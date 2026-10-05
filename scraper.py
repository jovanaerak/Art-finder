import asyncio
import time
from pydantic import BaseModel, Field
import instructor
from openai import AsyncOpenAI
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

from prefilter import classify_page, build_focused_context, looks_like_a_date

# NOTE: Update this if your WSL gateway IP changes (check with `ip route` in WSL).
OLLAMA_BASE_URL = "http://172.25.240.1:11434/v1"

_BROWSER_CONFIG = BrowserConfig(verbose=False)


class ArtOpportunity(BaseModel):
    title: str = Field(description="The name of the exhibition or call. Keep to one short line.")
    deadline: str = Field(
        description=(
            "The exact submission deadline as a specific calendar date, e.g. "
            "'March 1, 2027' or '10/31/2026'. If the page does not state one exact "
            "date (only a vague description, a range, or a recurring/rolling schedule), "
            "respond with exactly 'Not specified'. Do NOT describe the schedule in prose."
        )
    )
    age_requirement: str = Field(description="Age limits in a few words, e.g. '18+' or 'None'")
    eligibility: str = Field(description="Who can apply, in one short phrase (e.g. 'Georgia residents, grades 9-12')")
    mediums_accepted: list[str] = Field(description="Short list of accepted mediums (e.g. Oil, Photography)")
    entry_fee: str = Field(description="Cost to enter in a few words, e.g. 'Free' or '$15'")


class CrawlFailed(Exception):
    """Raised when a page can't be crawled or has no usable content."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def crawl_page(url: str) -> str:
    """
    Cheap step: fetch + scrape a page, return its markdown.
    No AI involved. Raises CrawlFailed on empty/failed scrapes.
    """
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=0, max_pages=1),
        verbose=False,
    )

    async with AsyncWebCrawler(config=_BROWSER_CONFIG) as crawler:
        results = await crawler.arun(url=url, config=config)

        if isinstance(results, list):
            combined_markdown = "\n\n".join([res.markdown for res in results if res.markdown])
        else:
            combined_markdown = results.markdown or ""

    if not combined_markdown.strip():
        raise CrawlFailed("no content scraped")

    return combined_markdown


async def analyze_with_ai(url: str, markdown: str) -> dict:
    """
    Expensive step: send (already crawled, already pre-filtered) markdown to
    the local AI for structured extraction. Assumes the caller has already
    confirmed this page is worth analyzing (e.g. via prefilter.classify_page
    returning "future_deadline").
    """
    focused_context = build_focused_context(markdown, max_total_chars=6000)

    client = instructor.from_openai(
        AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            timeout=120.0
        ),
        mode=instructor.Mode.MD_JSON,
    )

    prompt = (
        "Read the following website content for an art call and extract the details. "
        "The content may include multiple excerpts from different parts of the page, "
        "separated by '...'. Be concise: short phrases, not full sentences. "
        "For the deadline field specifically, only give an exact calendar date, "
        "or 'Not specified' if the page doesn't state one.\n\n" + focused_context
    )

    start = time.monotonic()
    extracted_data = await client.chat.completions.create(
        model="qwen2.5:3b",
        response_model=ArtOpportunity,
        messages=[{"role": "user", "content": prompt}],
        max_retries=2,
        temperature=0.0,
        max_tokens=400,
    )
    elapsed = time.monotonic() - start

    deadline_needs_review = not looks_like_a_date(extracted_data.deadline)

    return {
        "url": url,
        "title": extracted_data.title,
        "deadline": extracted_data.deadline,
        "deadline_needs_review": deadline_needs_review,
        "age_requirement": extracted_data.age_requirement,
        "eligibility": extracted_data.eligibility,
        "mediums_accepted": extracted_data.mediums_accepted,
        "entry_fee": extracted_data.entry_fee,
        "_seconds": round(elapsed, 1),
    }


async def crawl_and_classify(url: str):
    """
    Convenience wrapper for the pre-filter stage: crawl a page and classify
    it, returning (markdown_or_None, classification_string).
    On any crawl error, returns (None, "crawl_failed").
    """
    try:
        markdown = await crawl_page(url)
    except CrawlFailed as e:
        return None, f"crawl_failed: {e.reason}"
    except Exception as e:
        return None, f"crawl_failed: {e}"

    classification, _dates = classify_page(markdown)
    return markdown, classification


async def _test_single_url():
    """Quick manual test for this file alone. Run `python main.py` for the full pipeline."""
    target_url = "https://athica.org/calls/"
    markdown, classification = await crawl_and_classify(target_url)
    print(f"Classification: {classification}")
    if classification == "future_deadline":
        data = await analyze_with_ai(target_url, markdown)
        print("\n--- EXTRACTED RESULTS ---")
        print(data)
    else:
        print("Would be skipped before reaching the AI.")


if __name__ == "__main__":
    asyncio.run(_test_single_url())