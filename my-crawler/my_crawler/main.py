"""
PartsOps Crawler — Playwright-based scraper for exist.ru, autodoc.ru, rossko.ru.

Usage:
    python -m my_crawler.main                    # interactive (browser visible)
    HEADLESS=1 python -m my_crawler.main         # headless (CI/CD)
    PROXY_URL=http://user:pass@host:port python -m my_crawler.main  # via proxy
    CLEAN_SCREENSHOTS=1 python -m my_crawler.main  # remove old debug screenshots
"""
import asyncio
import os
import sys
import glob
from datetime import timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings, Request
from .routes import router


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


def get_browser_profile_dir() -> str:
    """Return an isolated persistent browser profile for marketplace sessions."""
    configured = os.environ.get("BROWSER_PROFILE_DIR", "").strip()
    default = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".browser-profile")
    profile_dir = os.path.abspath(configured or default)
    os.makedirs(profile_dir, mode=0o700, exist_ok=True)
    return profile_dir


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
    print(f"Prepared {len(requests)} crawler tasks. Starting PlaywrightCrawler...")

    # -- Crawler configuration --
    headless_mode = is_headless()
    proxy_config = get_proxy_config()
    browser_profile_dir = get_browser_profile_dir()
    if proxy_config:
        print("Using configured proxy.")
    print(f"Using persistent browser profile: {browser_profile_dir}")

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
        # Retry & timeout settings
        max_request_retries=3,
        request_handler_timeout=timedelta(seconds=60),
        max_session_rotations=3,
        # Use playwright's built-in navigation timeout
        navigation_timeout=timedelta(seconds=30),
    )

    # -- Run --
    await crawler.run(requests)

    # -- Export results --
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    csv_path = os.path.join(results_dir, "aggregated_parts.csv")
    json_path = os.path.join(results_dir, "aggregated_parts.json")

    print("Scraping completed! Exporting collected data...")
    try:
        await crawler.export_data(csv_path)
        await crawler.export_data(json_path)
        print(f"Successfully exported results to:")
        print(f"  CSV:  {os.path.abspath(csv_path)}")
        print(f"  JSON: {os.path.abspath(json_path)}")
    except Exception as e:
        print(f"Failed to export data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
