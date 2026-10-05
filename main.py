import asyncio
import json
import time
from datetime import datetime
from difflib import SequenceMatcher

from discovery import discover_with_serper
from scraper import crawl_and_classify, analyze_with_ai
from prefilter import qualifies_for_ai
from dotenv import load_dotenv
load_dotenv()

RESULTS_PER_QUERY = 20  
TARGET_PER_QUERY = 10    
CANDIDATE_BATCH_SIZE = 5
CRAWL_CONCURRENCY = CANDIDATE_BATCH_SIZE
AI_CONCURRENCY = 2

OUTPUT_FILE = "results.json"
TITLE_SIMILARITY_THRESHOLD = 0.7


async def gather_qualified_for_query(query: str, candidates: list, target: int):
    """Crawl and classify candidates for a given query, returning only those that qualify for AI analysis."""

    semaphore = asyncio.Semaphore(CRAWL_CONCURRENCY)
    qualified = []
    idx = 0

    async def guarded_crawl_and_classify(url):
        async with semaphore:
            return await crawl_and_classify(url)

    while idx < len(candidates) and len(qualified) < target:
        remaining_need = target - len(qualified)
        batch = candidates[idx: idx + max(remaining_need, CANDIDATE_BATCH_SIZE)]
        idx += len(batch)

        batch_results = await asyncio.gather(
            *[guarded_crawl_and_classify(c["url"]) for c in batch]
        )

        for candidate, (markdown, classification) in zip(batch, batch_results):
            url = candidate["url"]
            if qualifies_for_ai(classification) and len(qualified) < target:
                qualified.append({"url": url, "markdown": markdown})
                print(f"[QUALIFIED] {url}  ({classification})")
            else:
                print(f"[SKIPPED]   {url}  ({classification})")

    if len(qualified) < target:
        print(f"  -- '{query}': only found {len(qualified)}/{target} qualifying pages "
              f"out of {min(idx, len(candidates))} candidates checked.")

    return qualified


async def run_ai_stage(qualified_pages: list):
    """Run the expensive AI extraction on every qualifying page, with limited concurrency."""
    semaphore = asyncio.Semaphore(AI_CONCURRENCY)

    async def guarded_analyze(page):
        async with semaphore:
            try:
                result = await analyze_with_ai(page["url"], page["markdown"])
                print(f"[OK]     {page['url']}  ({result['_seconds']}s)")
                return result
            except Exception as e:
                print(f"[FAILED] {page['url']}  -> {e}")
                return None

    results = await asyncio.gather(*[guarded_analyze(p) for p in qualified_pages])
    return [r for r in results if r is not None]


def dedupe_by_title(results):
    """Collapse results that are almost certainly the same competition, based
    on title similarity (the same contest often lives at multiple URLs)."""
    kept = []

    for candidate in results:
        matched_existing = None
        for existing in kept:
            similarity = SequenceMatcher(
                None, candidate["title"].lower(), existing["title"].lower()
            ).ratio()
            if similarity >= TITLE_SIMILARITY_THRESHOLD:
                matched_existing = existing
                break

        if matched_existing is None:
            kept.append(candidate)
            continue

        existing_has_date = matched_existing["deadline"].lower() != "not specified"
        candidate_has_date = candidate["deadline"].lower() != "not specified"

        if candidate_has_date and not existing_has_date:
            kept.remove(matched_existing)
            kept.append(candidate)
            print(f"[DEDUPED] Kept '{candidate['title']}' from {candidate['url']} "
                  f"over {matched_existing['url']}")
        else:
            print(f"[DEDUPED] Dropped '{candidate['title']}' from {candidate['url']} "
                  f"as a likely duplicate of {matched_existing['url']}")

    return kept


def save_results(results):
    payload = {
        "generated_at": datetime.now().isoformat(),
        "count": len(results),
        "results": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} results to {OUTPUT_FILE}")


async def main():
    queries = [
        "Apply for art competitions 2027",
        "National art competition 2027 All Ages",
    ]

    pipeline_start = time.monotonic()

    # Stage 0: discovery, grouped per query
    grouped = discover_with_serper(queries, results_per_query=RESULTS_PER_QUERY)

    # Stage 1: cheap crawl+classify with rotation/backfill, per query
    all_qualified = []
    for query, candidates in grouped.items():
        print(f"\n--- Rotating through candidates for: '{query}' ---")
        qualified = await gather_qualified_for_query(query, candidates, TARGET_PER_QUERY)
        all_qualified.extend(qualified)

    print(f"\n{len(all_qualified)} pages qualified for AI analysis "
          f"(out of {sum(len(v) for v in grouped.values())} discovered).")

    # Stage 2: expensive AI extraction, only on qualifying pages
    ai_results = await run_ai_stage(all_qualified)

    # Stage 3: dedupe near-identical results
    final_results = dedupe_by_title(ai_results)

    total_seconds = time.monotonic() - pipeline_start

    print(f"\n--- PIPELINE COMPLETE ---")
    print(f"Total wall-clock time: {total_seconds:.1f}s")
    print(f"Final result count after dedup: {len(final_results)}\n")

    for item in final_results:
        review_flag = "  [NEEDS REVIEW]" if item.get("deadline_needs_review") else ""
        print(f"Title:       {item['title']}")
        print(f"URL:         {item['url']}")
        print(f"Deadline:    {item['deadline']}{review_flag}")
        print(f"Eligibility: {item['eligibility']}")
        print(f"Fee:         {item['entry_fee']}")
        print(f"Mediums:     {', '.join(item['mediums_accepted'])}")
        print()

    save_results(final_results)


if __name__ == "__main__":
    asyncio.run(main())