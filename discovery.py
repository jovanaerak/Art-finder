import os
import time
import requests
from dotenv import load_dotenv
load_dotenv()

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")


def discover_with_serper(search_queries, results_per_query=20, delay=1.0):
    """
    Returns a dict: {query: [ {url, title, snippet, source_query}, ... ]}

    Results are grouped PER QUERY (not merged into one flat list), in the
    order Serper returned them, so main.py can implement a per-query
    rotation/backfill system (take the first N that pass a filter, pull
    replacements from further down the list as needed).

    A URL that already appeared under an earlier query is skipped when it
    shows up again under a later query, so the same page is never crawled
    twice.
    """
    if not SERPER_API_KEY:
        raise ValueError(
            "SERPER_API_KEY environment variable not set. "
            "Set it before running this script."
        )

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    grouped_results = {}
    seen_urls = set()

    print("Starting Serper Google Search discovery engine...\n")

    for query in search_queries:
        print(f"Searching for: '{query}'")
        payload = {"q": query, "num": results_per_query}
        query_results = []

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])

                for item in results:
                    link = item.get("link")
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    query_results.append({
                        "url": link,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "source_query": query,
                    })
                    print(f"  [+] Found: {link}")
            elif response.status_code == 429:
                print("  [-] Rate limited by Serper. Waiting before continuing...")
                time.sleep(5)
            else:
                print(f"  [-] Serper Error {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            print("  [-] Request timed out.")
        except Exception as e:
            print(f"  [-] Request Failed: {e}")

        grouped_results[query] = query_results
        time.sleep(delay)

    total = sum(len(v) for v in grouped_results.values())
    print(f"\n--- SERPER DISCOVERY COMPLETE ---")
    print(f"Collected {total} unique URLs across {len(search_queries)} queries.")

    return grouped_results


if __name__ == "__main__":
    queries = ["georgia art competition"]
    grouped = discover_with_serper(queries)
    for query, items in grouped.items():
        print(f"\n{query}: {len(items)} results")
        for r in items:
            print(f"  {r['url']}")