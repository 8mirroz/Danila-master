"""
Conservative self-healing policy for crawler sources.

Bounded retries, one-step fallbacks, never hidden infinite recovery.
Every fallback path used is recorded for the run report.
"""

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception classification  (stable, bounded set)
# ---------------------------------------------------------------------------

EXCEPTION_CATEGORIES = frozenset({
    "network_error",
    "anti_bot",
    "layout_changed",
    "auth_required",
    "timeout",
    "unknown",
})


def classify_error(exc: Exception) -> str:
    """Map an exception to a stable category."""
    exc_name = type(exc).__name__
    exc_msg = str(exc).lower()

    # Timeout
    if "timeout" in exc_name.lower() or "timeout" in exc_msg:
        return "timeout"

    # Network errors
    if any(kw in exc_name.lower() for kw in ("connection", "dns", "socket", "http")):
        return "network_error"
    if any(kw in exc_msg for kw in ("connection refused", "dns resolution", "network", "econnrefused", "enotfound")):
        return "network_error"

    # Anti-bot / blocked
    if any(kw in exc_msg for kw in ("captcha", "blocked", "403", "429", "too many requests", "access denied")):
        return "anti_bot"

    # Auth required
    if any(kw in exc_msg for kw in ("login", "auth", "unauthorized", "401", "session expired")):
        return "auth_required"

    # Layout changed (selector not found, element missing)
    if any(kw in exc_name.lower() for kw in ("selector", "element", "locator", "notfound")):
        return "layout_changed"
    if any(kw in exc_msg for kw in ("no such element", "element not found", "locator not found")):
        return "layout_changed"

    return "unknown"


# ---------------------------------------------------------------------------
# Bounded retry
# ---------------------------------------------------------------------------

async def bounded_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 2,
    site: str = "",
    fallback_paths: Optional[list[str]] = None,
    **kwargs: Any,
) -> tuple[Any, bool, list[str]]:
    """Execute an async callable with bounded retries.

    Args:
        fn: Async callable to execute.
        max_retries: Maximum number of retry attempts (default 2).
        site: Site label for logging.
        fallback_paths: Mutable list to record fallback paths used.
        *args, **kwargs: Passed to fn.

    Returns:
        Tuple of (result, succeeded, fallback_paths_used).
        result is None if all retries failed.
    """
    if fallback_paths is None:
        fallback_paths = []

    last_exc: Optional[Exception] = None
    attempt = 0

    while attempt <= max_retries:
        try:
            result = await fn(*args, **kwargs)
            if attempt > 0:
                path = f"retry_{attempt}/{max_retries}"
                if path not in fallback_paths:
                    fallback_paths.append(path)
                logger.info(f"[{site}] Succeeded on {path}")
            return result, True, fallback_paths
        except Exception as exc:
            last_exc = exc
            category = classify_error(exc)
            attempt += 1
            logger.warning(
                f"[{site}] Attempt {attempt}/{max_retries + 1} failed: "
                f"[{category}] {exc}"
            )
            if attempt <= max_retries:
                # Exponential backoff: 2s, 4s
                wait = 2 ** attempt
                logger.info(f"[{site}] Waiting {wait}s before retry...")
                await asyncio.sleep(wait)

    # All retries exhausted
    path = f"retry_exhausted_{max_retries + 1}"
    if path not in fallback_paths:
        fallback_paths.append(path)
    logger.error(f"[{site}] All {max_retries + 1} attempts failed: {last_exc}")
    return None, False, fallback_paths


# ---------------------------------------------------------------------------
# Autodoc-specific healing
# ---------------------------------------------------------------------------

async def autodoc_search_with_fallback(context: Any, article: str) -> tuple[bool, list[str]]:
    """Perform Autodoc search with fallback paths.

    Tries Enter first; if no /price/ links appear, clicks search button once.
    Returns (success, fallback_paths_used).
    """
    fallback_paths: list[str] = []
    from .routes import AUTODOC_SEARCH_INPUT_SELECTOR, AUTODOC_SEARCH_BUTTON_SELECTOR

    page = context.page

    # Step 1: Find search input
    search_input = page.locator(AUTODOC_SEARCH_INPUT_SELECTOR).first
    try:
        await search_input.wait_for(state="visible", timeout=12_000)
    except Exception:
        fallback_paths.append("search_input_not_found")
        return False, fallback_paths

    await search_input.click()
    await search_input.fill(article)
    await page.wait_for_timeout(500)

    # Step 2: Press Enter
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(700)

    # Step 3: Check for /price/ links
    price_links = page.locator('a[href*="/price/"]')
    try:
        await price_links.first.wait_for(state="visible", timeout=5_000)
        return True, fallback_paths
    except Exception:
        pass

    # Step 4: Fallback — click search button
    search_button = page.locator(AUTODOC_SEARCH_BUTTON_SELECTOR).first
    try:
        if await search_button.count():
            fallback_paths.append("search_button_fallback")
            await search_button.click(timeout=3_000)
            await page.wait_for_timeout(1_000)
            # Check again for /price/ links
            try:
                await price_links.first.wait_for(state="visible", timeout=5_000)
                return True, fallback_paths
            except Exception:
                pass
    except Exception:
        pass

    fallback_paths.append("no_price_links_after_fallback")
    return False, fallback_paths


async def autodoc_wait_for_locator(
    context: Any,
    selector: str,
    timeout: int = 12_000,
) -> bool:
    """Wait for a locator to be visible. Returns True if found."""
    try:
        locator = context.page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Rossko-specific healing
# ---------------------------------------------------------------------------

async def rossko_extended_wait(context: Any, article: str) -> tuple[bool, list[str]]:
    """Extended wait + single-page reload for Rossko.

    Returns (success, fallback_paths_used).
    """
    fallback_paths: list[str] = []
    page = context.page

    # Initial wait
    await page.wait_for_timeout(5_000)

    # Check for result links
    item_links = await page.query_selector_all('a[class*="result-item-"][class*="link"]')
    if item_links:
        return True, fallback_paths

    # Extended wait
    fallback_paths.append("extended_wait")
    await page.wait_for_timeout(5_000)
    item_links = await page.query_selector_all('a[class*="result-item-"][class*="link"]')
    if item_links:
        return True, fallback_paths

    # Single-page reload
    fallback_paths.append("page_reload")
    await page.reload()
    await page.wait_for_timeout(5_000)
    item_links = await page.query_selector_all('a[class*="result-item-"][class*="link"]')
    if item_links:
        return True, fallback_paths

    return False, fallback_paths


async def rossko_retry_via_proxy(
    context: Any,
    article: str,
    proxy_url: str,
) -> tuple[bool, list[str]]:
    """Retry Rossko through a proxy. Used once if result rows missing.

    Returns (success, fallback_paths_used).
    """
    fallback_paths: list[str] = ["proxy_fallback"]
    logger.info(f"[rossko] Retrying article {article} via proxy fallback")
    # The actual proxy retry is handled by the orchestrator creating a new context
    # with proxy. This function records the fallback path.
    return False, fallback_paths


def rossko_classify_empty(page_html: str) -> str:
    """Classify an empty Rossko result page.

    Returns one of: 'search_empty', 'layout_changed', 'unknown'.
    """
    html_lower = page_html.lower()
    if "ничего не найдено" in html_lower:
        return "search_empty"
    if "капча" in html_lower or "captcha" in html_lower:
        return "anti_bot"
    if "вход" in html_lower or "войти" in html_lower or "login" in html_lower:
        return "auth_required"
    return "layout_changed"


# ---------------------------------------------------------------------------
# Exist-specific healing
# ---------------------------------------------------------------------------

async def exist_reload_and_settle(context: Any, url: str) -> tuple[bool, list[str]]:
    """Reload and wait for Exist price page to settle.

    Returns (success, fallback_paths_used).
    """
    fallback_paths: list[str] = []
    page = context.page

    fallback_paths.append("reload_and_settle")
    await page.reload()
    await page.wait_for_timeout(5_000)

    # Check for row containers
    row_containers = await page.query_selector_all(".row-container")
    if row_containers:
        return True, fallback_paths

    return False, fallback_paths


def exist_classify_empty(url: str, page_html: str) -> str:
    """Classify an empty Exist result page.

    Returns one of: 'no_results', 'layout_changed', 'auth_required', 'unknown'.
    """
    html_lower = page_html.lower()
    if "404" in html_lower or "страница не найдена" in html_lower:
        return "no_results"
    if "вход" in html_lower or "войти" in html_lower or "login" in html_lower:
        return "auth_required"
    if "капча" in html_lower or "captcha" in html_lower:
        return "anti_bot"
    # Check if catalog page (not a price page)
    if 'class="catalogs"' in html_lower or 'ul class="catalogs"' in html_lower:
        return "no_results"
    return "layout_changed"