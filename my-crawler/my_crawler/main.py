"""
PartsOps Crawler — Playwright-based scraper for exist.ru, autodoc.ru, rossko.ru.

Usage:
    python -m my_crawler.main                    # interactive (browser visible)
    HEADLESS=1 python -m my_crawler.main         # headless (CI/CD)
    PROXY_URL=http://user:pass@host:port python -m my_crawler.main  # via proxy
    CLEAN_SCREENSHOTS=1 python -m my_crawler.main  # remove old debug screenshots
"""
import asyncio
import csv
import json
import os
import sys
import glob
from pathlib import Path
from datetime import timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee.configuration import Configuration
from crawlee import ConcurrencySettings, Request
from .routes import router

SITE_LABELS = ("exist", "autodoc", "rossko")
SITE_ENV_PREFIX = {
    "exist": "EXIST",
    "autodoc": "AUTODOC",
    "rossko": "ROSSKO",
}


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def is_headless() -> bool:
    """Check if HEADLESS env var is set to a truthy value."""
    val = os.environ.get("HEADLESS", "").strip().lower()
    return val in ("1", "true", "yes", "y")


def get_proxy_config() -> dict | None:
    """Read PROXY_URL env var and return Playwright proxy config dict, or None."""
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    if not proxy_url:
        return None
    return {"server": proxy_url}


def ensure_dir(path: str) -> str:
    """Create directory if needed and return its absolute path."""
    profile_dir = os.path.abspath(path)
    os.makedirs(profile_dir, mode=0o700, exist_ok=True)
    return profile_dir


def get_browser_profile_dir(site: str | None = None) -> str:
    """Return a persistent browser profile, optionally overridden per marketplace."""
    configured = os.environ.get("BROWSER_PROFILE_DIR", "").strip()
    default = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".browser-profile")
    if site:
        env_prefix = SITE_ENV_PREFIX[site]
        site_configured = os.environ.get(f"{env_prefix}_BROWSER_PROFILE_DIR", "").strip()
        if site_configured:
            return ensure_dir(site_configured)
    return ensure_dir(configured or default)


def get_proxy_config_for_site(site: str) -> dict | None:
    """Return proxy config, allowing site-specific override over global PROXY_URL."""
    env_prefix = SITE_ENV_PREFIX[site]
    proxy_url = os.environ.get(f"{env_prefix}_PROXY_URL", "").strip()
    if proxy_url:
        return {"server": proxy_url}
    return get_proxy_config()


def get_max_concurrency() -> int:
    """Bound parallel tabs to preserve marketplace sessions and avoid rate spikes."""
    value = os.environ.get("CRAWLER_MAX_CONCURRENCY", "2").strip()
    try:
        return max(1, min(int(value), 4))
    except ValueError:
        return 2


def should_clean_screenshots() -> bool:
    """Check if CLEAN_SCREENSHOTS env var is set."""
    val = os.environ.get("CLEAN_SCREENSHOTS", "").strip().lower()
    return val in ("1", "true", "yes", "y")


def clean_old_screenshots(directory: str = ".") -> int:
    """Remove old debug screenshot PNGs. Returns count of removed files."""
    pattern = os.path.join(directory, "*_debug.png")
    files = glob.glob(pattern)
    for f in files:
        try:
            os.remove(f)
        except OSError:
            pass
    return len(files)


def resolve_articles_path() -> str:
    """Find articles.txt in cwd or package directory."""
    candidates = [
        os.environ.get("ARTICLES_FILE", ""),
        "articles.txt",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "articles.txt"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    print("Error: articles.txt file not found! Please create it in the project root.")
    sys.exit(1)


def load_articles(path: str) -> list[str]:
    """Load non-empty, non-comment lines from articles.txt."""
    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


def build_requests(articles: list[str]) -> list[Request]:
    """Build crawler requests for each article across all 3 marketplaces."""
    requests = []
    for article in articles:
        article_lower = article.lower()

        # 1. Exist.ru — direct URL, no hash issues
        requests.append(
            Request.from_url(
                url=f"https://www.exist.ru/Price/?pcode={article}",
                label="exist",
                user_data={"article": article},
            )
        )

        # 2. Autodoc.ru — use a landing page, then search via JS in the handler.
        #    Hash fragments (#search-xxx) are ignored by Playwright, so we
        #    navigate to the main page and let the handler perform the search.
        requests.append(
            Request.from_url(
                url="https://www.autodoc.ru/",
                label="autodoc",
                user_data={"article": article_lower},
            )
        )

        # 3. Rossko.ru
        requests.append(
            Request.from_url(
                url=f"https://sochi.rossko.ru/search?q={article_lower}&text={article_lower}&type=all",
                label="rossko",
                user_data={"article": article},
            )
        )

    return requests


def partition_requests_by_site(requests: list[Request]) -> dict[str, list[Request]]:
    """Split crawler requests into site-specific batches."""
    batches = {site: [] for site in SITE_LABELS}
    for request in requests:
        if request.label in batches:
            batches[request.label].append(request)
    return batches


def get_site_storage_dir(site: str) -> str:
    """Return isolated Crawlee storage dir for one marketplace run."""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", site)
    return ensure_dir(base)


def export_results(records: list[dict], results_dir: str = "results") -> tuple[str, str]:
    """Export aggregated records to JSON and CSV."""
    os.makedirs(results_dir, exist_ok=True)
    csv_path = os.path.join(results_dir, "aggregated_parts.csv")
    json_path = os.path.join(results_dir, "aggregated_parts.json")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)

    fieldnames: list[str] = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or ["site"], extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    return csv_path, json_path


async def run_site_crawler(site: str, requests: list[Request], headless_mode: bool) -> list[dict]:
    """Run one marketplace batch with its own persistent profile and isolated storage."""
    if not requests:
        return []

    proxy_config = get_proxy_config_for_site(site)
    browser_profile_dir = get_browser_profile_dir(site)
    storage_dir = get_site_storage_dir(site)
    if proxy_config:
        print(f"[{site}] Using configured proxy.")
    print(f"[{site}] Using persistent browser profile: {browser_profile_dir}")

    crawler = PlaywrightCrawler(
        request_handler=router,
        headless=headless_mode,
        user_data_dir=browser_profile_dir,
        use_incognito_pages=False,
        max_requests_per_crawl=100,
        concurrency_settings=ConcurrencySettings(
            min_concurrency=1,
            desired_concurrency=get_max_concurrency(),
            max_concurrency=get_max_concurrency(),
        ),
        browser_type="chromium",
        browser_new_context_options={
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1920, "height": 1080},
            "proxy": proxy_config,
        },
        max_request_retries=3,
        request_handler_timeout=timedelta(seconds=60),
        max_session_rotations=3,
        navigation_timeout=timedelta(seconds=30),
        configuration=Configuration(
            storage_dir=storage_dir,
            purge_on_start=True,
            headless=headless_mode,
        ),
    )

    await crawler.run(requests)
    dataset_page = await crawler.get_data(limit=10_000)
    return list(dataset_page.items)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    """The crawler entry point."""

    # -- Clean old screenshots if requested --
    if should_clean_screenshots():
        removed = clean_old_screenshots()
        print(f"Cleaned {removed} old debug screenshot(s).")

    # -- Load articles --
    articles_path = resolve_articles_path()
    print(f"Reading articles from: {os.path.abspath(articles_path)}")
    articles = load_articles(articles_path)

    if not articles:
        print("No articles found in articles.txt!")
        sys.exit(1)

    print(f"Found {len(articles)} articles to scrape: {articles}")

    # -- Build requests --
    requests = build_requests(articles)
    print(f"Prepared {len(requests)} crawler tasks. Starting site-specific crawler runs...")

    # -- Crawler configuration --
    headless_mode = is_headless()
    request_batches = partition_requests_by_site(requests)
    collected_records: list[dict] = []
    for site in SITE_LABELS:
        site_requests = request_batches[site]
        if not site_requests:
            continue
        print(f"[{site}] Running {len(site_requests)} request(s)")
        site_records = await run_site_crawler(site, site_requests, headless_mode)
        print(f"[{site}] Collected {len(site_records)} record(s)")
        collected_records.extend(site_records)

    # -- Export results --
    print("Scraping completed! Exporting collected data...")
    try:
        csv_path, json_path = export_results(collected_records)
        print(f"Successfully exported results to:")
        print(f"  CSV:  {os.path.abspath(csv_path)}")
        print(f"  JSON: {os.path.abspath(json_path)}")
    except Exception as e:
        print(f"Failed to export data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
