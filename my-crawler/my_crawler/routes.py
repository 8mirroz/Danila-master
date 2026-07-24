import re
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router
from crawlee import Request

router = Router[PlaywrightCrawlingContext]()

AUTODOC_SEARCH_INPUT_SELECTOR = 'input[type="search"]:visible'
AUTODOC_SEARCH_BUTTON_SELECTOR = 'button.search-button:visible, button:has-text("Найти"):visible'
AUTODOC_RESULT_ROW_SELECTOR = '.pgoods'


def resolve_rossko_card_url(href: str | None, base_url: str) -> str | None:
    """Return a same-site Rossko internal product-card URL, or None for a search URL."""
    if not href:
        return None
    url = urljoin(base_url, href)
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith("rossko.ru") and (
        parsed.path.startswith("/card/") or parsed.path == "/product"
    ):
        return url
    return None


def rossko_card_has_product_data(title: str, price_node_count: int) -> bool:
    """Reject the empty Rossko shell that renders without any product pricing."""
    return bool(title.strip()) and price_node_count > 0


def is_autodoc_price_link(href: str | None) -> bool:
    """Return True for Autodoc product-price routes."""
    return bool(href and "/price/" in href)


def normalize_part_token(value: str | None) -> str:
    """Normalize article/brand tokens for fuzzy matching across vendor formatting."""
    return re.sub(r'[^A-Z0-9]+', '', (value or '').upper())


def split_autodoc_title(title: str, fallback_article: str = "") -> tuple[str, str, str]:
    """Split an Autodoc row title into brand, article, description."""
    text = re.sub(r'\s+', ' ', (title or '').strip())
    if not text:
        return "Autodoc Match", fallback_article, ""

    tokens = text.split()
    article_tokens: list[str] = []
    for idx in range(len(tokens) - 1, -1, -1):
        token = tokens[idx]
        if re.search(r'\d', token) or article_tokens:
            article_tokens.insert(0, token)
            if normalize_part_token(" ".join(article_tokens)) == normalize_part_token(fallback_article):
                break
        else:
            break

    article = " ".join(article_tokens).strip() or fallback_article
    core_tokens = tokens[: len(tokens) - len(article_tokens)] if article_tokens else tokens

    brand_tokens: list[str] = []
    description_tokens: list[str] = []
    seen_description = False
    for token in core_tokens:
        letters = re.sub(r'[^A-Za-zА-Яа-яЁё]+', '', token)
        is_brandish = bool(letters) and letters == letters.upper()
        if not seen_description and (is_brandish or token in {"|", "/", "&"}):
            brand_tokens.append(token)
            continue
        seen_description = True
        description_tokens.append(token)

    brand = " ".join(brand_tokens).strip(" |/") or "Autodoc Match"
    description = " ".join(description_tokens).strip()
    if not description and brand != text:
        description = text.replace(brand, "", 1).replace(article, "", 1).strip(" |-")

    return brand, article, description


def extract_autodoc_stock(row_text: str, offers_class: str = "") -> str:
    """Extract stock/availability from a result row text."""
    text = re.sub(r'\s+', ' ', (row_text or '').strip())
    stock_match = re.search(r'(\d+\s*шт)', text, flags=re.IGNORECASE)
    if stock_match:
        return stock_match.group(1)
    if "недоступ" in text.lower() or "offers-closed" in offers_class:
        return "Unavailable"
    return "Unknown"


def extract_autodoc_delivery(row_text: str) -> str:
    """Extract delivery window from row text as a stable human-readable fragment."""
    text = re.sub(r'\s+', ' ', (row_text or '').strip())
    match = re.search(
        r'((?:от\s+)?\d+\s+(?:раб(?:оч(?:его|их))?\.?\s+)?дн(?:я|ей)|(?:от\s+)?\d+\s+рабоч(?:его|их)\s+дн(?:я|ей))',
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return "Standard Delivery"


def autodoc_row_score(title: str, row_text: str, catalog_brand: str, search_article: str) -> int:
    """Rank Autodoc result rows so the parser chooses the intended product first."""
    title_norm = normalize_part_token(title)
    brand_norm = normalize_part_token(catalog_brand)
    article_norm = normalize_part_token(search_article)
    score = 0
    if article_norm and article_norm in title_norm:
        score += 10
    if brand_norm and brand_norm in title_norm:
        score += 8
    if "₽" in row_text:
        score += 4
    if "недоступ" in row_text.lower():
        score -= 3
    return score


async def capture_price_evidence(context: PlaywrightCrawlingContext, site: str, article: str) -> dict:
    """Capture the rendered price page before publishing a price record."""
    os.makedirs("screenshots", exist_ok=True)
    filename = f"{site.replace('.', '_')}_{re.sub(r'[^A-Za-z0-9_-]', '_', article)}_{uuid.uuid4().hex}.png"
    path = os.path.join("screenshots", filename)
    await context.page.screenshot(path=path, full_page=True)
    return {
        "source_url": context.page.url or context.request.url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "screenshot_path": os.path.abspath(path),
    }

# Helper to clean up price strings to numbers
def clean_price(price_str: str) -> str:
    """Extract a clean price string from raw marketplace text.

    Handles formats:
        "4 500 ₽"       → "4500 ₽"
        "1 200,50 ₽"    → "1200.50 ₽"
        "4500"          → "4500 ₽"
        "471,15 ₽  1 418 20" → "471.15 ₽"
        "——"            → "——"
    """
    if not price_str or price_str == "——":
        return "——"

    # Step 1: collapse all whitespace around digits — remove spaces between digits
    # so "4 500" becomes "4500" but "1 200,50" becomes "1200,50"
    s = price_str.replace("\xa0", " ")
    s = re.sub(r'(?<=\d)\s+(?=\d)', '', s)
    s = s.replace("–", "-")

    # Step 2: find the price pattern: digits (with optional decimal , or .) near ₽
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*₽', s)
    if m:
        return m.group(1).replace(",", ".") + " ₽"

    # Try: ₽ before digits
    m = re.search(r'₽\s*(\d+(?:[.,]\d+)?)', s)
    if m:
        return m.group(1).replace(",", ".") + " ₽"

    # Step 3: first continuous digit group (no ₽ symbol in string)
    digits = re.findall(r'\d+', s)
    if digits:
        return digits[0] + " ₽"

    if "₽" in s:
        return "——"

    return price_str

@router.handler('exist')
async def handle_exist(context: PlaywrightCrawlingContext) -> None:
    """Handler for Exist.ru search and price pages."""
    url = context.request.url
    article = context.request.user_data.get('article', '')
    context.log.info(f'Processing Exist.ru request for article: {article} (URL: {url})')

    # Wait for the main page content to settle
    await context.page.wait_for_timeout(3000)

    # 1. Check if we are on the catalog selection page
    catalog_links = await context.page.query_selector_all("ul.catalogs a")
    if catalog_links:
        context.log.info(f'Found {len(catalog_links)} catalog options on Exist.ru. Enqueuing them...')
        requests_to_add = []
        for link in catalog_links:
            text = (await link.inner_text()).strip().replace("\n", " ")
            href = await link.get_attribute("href")
            if href:
                full_url = f"https://www.exist.ru{href}" if href.startswith("/") else href
                requests_to_add.append(
                    Request.from_url(
                        url=full_url,
                        label='exist',
                        user_data={'article': article, 'catalog_brand': text}
                    )
                )
        if requests_to_add:
            await context.add_requests(requests_to_add)
        return

    # 2. Otherwise, we are on the price page
    # Find all row containers (for both original and analog parts)
    row_containers = await context.page.query_selector_all(".row-container")
    if not row_containers:
        context.log.warning(f"No price rows found on Exist.ru for URL: {url}")
        # Save a debug screenshot
        await context.page.screenshot(path="exist_no_rows_debug.png")
        return

    # Known brands list to help extract brand from description on Exist.ru
    EXIST_KNOWN_BRANDS = [
        "TRW", "ATE", "NGK", "Brembo", "Bosch", "Mann", "Mann-Filter", "MANN-FILTER",
        "Mahle", "Knecht", "Knecht Filter", "Hengst", "Finwhale", "SCT", "WIX", "Mapco",
        "MecaFilter", "VAG", "Valeo", "Febi", "Meyle", "Topran", "Fram", "Champion",
        "Blue Print", "AM Point", "AM POINT", "Sakura", "Filtron", "Bosch", "Ufi",
        "Kolbenschmidt", "General Motors", "Daewoo", "Opel", "Isuzu", "Ford",
        "Mitsubishi", "Honda", "Mazda", "Fiat/Alfa/Lancia", "Hyundai/Kia", "Volvo",
        "Citroen/Peugeot", "Great wall", "Chery",
        "Part-One", "Metaco", "Tatsumi", "Eurorepar", "Patron", "Ganz", "Unio",
        "Diforza", "Pilenga", "Autorepar", "Amd", "Cworks", "Green filter",
        "Miles", "Nakayama", "Carville Racing", "Goodwill", "BIG Filter",
        "Raf filter", "Skyparts", "Fortech", "Korwin", "Segmatic", "Avantech",
        "Lecar", "Wego", "Zekkert", "Logem", "Denckermann", "GParts", "Rospart",
        "Rb-exide", "Marshall", "Sampiyon filtre", "Profix", "Absel", "Caready",
        "Amiwa", "Frey", "LYNXauto", "UBS", "Totachi", "Tesla Technics",
        "Zentparts", "Sumomoto", "Mfilter", "Quattro freni", "Che Shuang",
        "Komtechnology", "Misfat", "Oechi", "PSV", "Comline", "JHF", "Schatz",
        "Nordfil", "Riginal", "Trucktec", "Alco", "Alpic", "Tadashisa",
        "Borsehung", "Jp Group", "Manbo", "Goodyear", "Tecneco", "Maxgear",
        "Lucas filters", "AgatFilter", "Meat&Doria", "Bremsi", "Hart",
        "Magneti marelli", "Kraft Automotive", "Vaico", "Fiaam",
        "S&K GmbH", "Arirang", "ANYU", "Redrex", "Asin", "BM",
        "Dominant", "Dynamatrix", "Vika", "JD", "Phoenix", "Support Technology",
        "Mobiland", "Sat", "Iberis", "Hola", "Narichin", "Brave", "BSG",
        "LivCar", "Sufix", "Nac", "Невский фильтр", "Double force",
        "Мавико", "Stellox", "Hans Pries", "Borsehung",
    ]

    context.log.info(f"Found {len(row_containers)} part matches on Exist.ru")
    page_evidence = await capture_price_evidence(context, "exist_ru", article)
    for container in row_containers:
        # Extract Brand — try multiple selectors
        brand = "Unknown"
        for sel in [".row .name-container b", ".row .name-container strong",
                     ".row .name-container a", "[class*=brand]"]:
            brand_el = await container.query_selector(sel)
            if brand_el:
                brand = (await brand_el.inner_text()).strip()
                if brand:
                    break

        # Extract Article/Part Number
        partno_el = await container.query_selector(".row .partno")
        matched_article = (await partno_el.inner_text()).strip() if partno_el else ""

        # Extract Description
        name_container = await container.query_selector(".row .name-container")
        description = ""
        full_name_text = ""
        if name_container:
            full_name_text = (await name_container.inner_text()).strip().replace("\n", " ")
            description = full_name_text.replace(brand, "").replace(matched_article, "").strip()

        # Fallback: if brand still Unknown, try to extract brand from description
        # by matching against known brands list
        if brand == "Unknown" and full_name_text:
            for kb in sorted(EXIST_KNOWN_BRANDS, key=len, reverse=True):
                if kb.lower() in full_name_text.lower():
                    brand = kb
                    description = full_name_text.replace(brand, "").replace(matched_article, "").strip()
                    break

        # If still Unknown, use first word of description as brand hint
        if brand == "Unknown" and description:
            words = description.split()
            if words:
                brand = words[0]
                description = " ".join(words[1:]).strip()

        # Extract Offers (price rows)
        price_rows = await container.query_selector_all(".pricerow, .pricerow--direct")
        for row in price_rows:
            # Delivery time
            delivery_el = await row.query_selector(".statis")
            delivery = (await delivery_el.inner_text()).strip().replace("\n", " ") if delivery_el else "Unknown"

            # Price
            price_el = await row.query_selector(".price")
            price_raw = (await price_el.inner_text()).strip() if price_el else ""
            price = clean_price(price_raw)

            if price == "——":
                continue
            # Store result
            await context.push_data({
                "site": "exist.ru",
                "search_article": article,
                "brand": brand,
                "article": matched_article,
                "description": description,
                "delivery": delivery,
                "price": price,
                **page_evidence,
            })

@router.handler('autodoc')
async def handle_autodoc(context: PlaywrightCrawlingContext) -> None:
    """Handler for Autodoc.ru home page to search and enqueue price pages."""
    article = context.request.user_data.get('article', '')
    context.log.info(f'Searching Autodoc.ru for article: {article}')

    search_input = context.page.locator(AUTODOC_SEARCH_INPUT_SELECTOR).first
    try:
        await search_input.wait_for(state="visible", timeout=12_000)
    except Exception:
        context.log.error("Could not find visible search input on Autodoc.ru")
        await context.page.screenshot(path="autodoc_no_input_debug.png")
        return

    await search_input.click()
    await search_input.fill(article)
    await context.page.wait_for_timeout(500)

    await context.page.keyboard.press("Enter")
    await context.page.wait_for_timeout(700)

    search_button = context.page.locator(AUTODOC_SEARCH_BUTTON_SELECTOR).first
    try:
        if await search_button.count() and not await context.page.locator('a[href*="/price/"]').count():
            await search_button.click(timeout=2_000)
    except Exception:
        context.log.warning("Could not click a visible Autodoc search button after Enter")

    try:
        await context.page.wait_for_function(
            """() => Array.from(document.querySelectorAll('a[href]'))
            .some((a) => a.getAttribute('href')?.includes('/price/'))""",
            timeout=10_000,
        )
    except Exception:
        context.log.warning(f"No search suggestions found on Autodoc.ru for article: {article}")
        await context.page.screenshot(path="autodoc_no_suggestions_debug.png")
        return

    raw_links = await context.page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href]')).map((a) => ({
            href: a.getAttribute('href'),
            text: (a.textContent || '').trim().replace(/\\s+/g, ' ')
        }));
    }""")
    suggestion_links = []
    seen_hrefs = set()
    for item in raw_links:
        href = item.get("href")
        if not is_autodoc_price_link(href) or href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        suggestion_links.append(item)

    if not suggestion_links:
        context.log.warning(f"No search suggestions found on Autodoc.ru for article: {article}")
        await context.page.screenshot(path="autodoc_no_suggestions_debug.png")
        return

    context.log.info(f"Found {len(suggestion_links)} suggestion links in Autodoc dropdown")
    requests_to_add = []
    for sugg in suggestion_links:
        full_url = f"https://www.autodoc.ru{sugg['href']}" if sugg['href'].startswith("/") else sugg['href']
        requests_to_add.append(
            Request.from_url(
                url=full_url,
                label='autodoc_price',
                user_data={'article': article, 'catalog_brand': sugg['text']}
            )
        )
    if requests_to_add:
        await context.add_requests(requests_to_add)

@router.handler('autodoc_price')
async def handle_autodoc_price(context: PlaywrightCrawlingContext) -> None:
    """Handler for Autodoc.ru product price pages."""
    url = context.request.url
    article = context.request.user_data.get('article', '')
    catalog_brand = context.request.user_data.get('catalog_brand', 'Autodoc Match')
    context.log.info(f'Processing Autodoc.ru price page: {url}')

    try:
        await context.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        await context.page.locator(AUTODOC_RESULT_ROW_SELECTOR).first.wait_for(state="visible", timeout=12_000)
    except Exception as exc:
        context.log.warning(f"Autodoc price card is unavailable after navigation: {url}; {exc}")
        context.log.error(f"Failed to load prices for Autodoc URL: {url}. Please resolve block or login if needed.")
        await context.page.screenshot(path="autodoc_price_load_failed.png")
        return

    rows = await context.page.locator(AUTODOC_RESULT_ROW_SELECTOR).all()
    candidates: list[dict] = []
    for row in rows:
        row_text = (await row.inner_text()).strip().replace("\n", " ")
        title_locator = row.locator(".card__title").first
        title_text = (await title_locator.inner_text()).strip().replace("\n", " ") if await title_locator.count() else ""
        if not row_text or not title_text:
            continue

        price_raw = ""
        for selector in (".offers__price", ".card__price-link", '[class*="offers__price"]'):
            locator = row.locator(selector).first
            if await locator.count():
                raw = (await locator.inner_text()).strip()
                if raw:
                    price_raw = raw
                    break
        if not price_raw:
            price_raw = row_text

        delivery_raw = ""
        for selector in (".offers__delivery-desktop", ".offers__delivery", '[class*="delivery"]'):
            locator = row.locator(selector).first
            if await locator.count():
                raw = (await locator.inner_text()).strip()
                if raw:
                    delivery_raw = raw
                    break

        offers_class = ""
        offers_locator = row.locator(".offers").first
        if await offers_locator.count():
            offers_class = await offers_locator.get_attribute("class") or ""

        candidates.append({
            "title": title_text,
            "row_text": row_text,
            "price": clean_price(price_raw),
            "delivery": delivery_raw or extract_autodoc_delivery(row_text),
            "stock": extract_autodoc_stock(row_text, offers_class),
            "score": autodoc_row_score(title_text, row_text, catalog_brand, article),
        })

    candidates = [candidate for candidate in candidates if candidate["price"] != "——"]
    if not candidates:
        context.log.error(f"Failed to extract priced rows for Autodoc URL: {url}")
        await context.page.screenshot(path="autodoc_price_load_failed.png")
        return

    best = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]
    precise_brand, matched_article, description = split_autodoc_title(best["title"], article)
    price = best["price"]
    delivery = best["delivery"]
    stock = best["stock"]

    if normalize_part_token(catalog_brand) and normalize_part_token(catalog_brand) not in normalize_part_token(best["title"]):
        precise_brand = catalog_brand

    if price == "——":
        return
    evidence = await capture_price_evidence(context, "autodoc_ru", article)

    await context.push_data({
        "site": "autodoc.ru",
        "search_article": article,
        "brand": precise_brand,
        "article": matched_article or article,
        "description": description or best["title"],
        "delivery": f"{delivery} (Stock: {stock})",
        "price": price,
        **evidence,
    })

@router.handler('rossko')
async def handle_rossko(context: PlaywrightCrawlingContext) -> None:
    """Handler for Rossko.ru search result pages."""
    url = context.request.url
    article = context.request.user_data.get('article', '')
    context.log.info(f'Processing Rossko.ru request for article: {article} (URL: {url})')

    # Wait for the results to load
    await context.page.wait_for_timeout(5000)

    # Find search result links (which represent rows in their grid/list)
    # The class format is prefix-link-suffix from CSS Modules. We select links containing brand and article
    item_links = await context.page.query_selector_all('a[class*="result-item-"][class*="link"]')
    if not item_links:
        # Fallback: check if there are any results at all
        no_results = await context.page.query_selector("text=Ничего не найдено")
        if no_results:
            context.log.warning(f"No matches found on Rossko.ru for article: {article}")
            return
        
        context.log.warning(f"No result rows found on Rossko.ru for URL: {url}. Retrying wait...")
        await context.page.wait_for_timeout(5000)
        item_links = await context.page.query_selector_all('a[class*="result-item-"][class*="link"]')

    if not item_links:
        context.log.error(f"Failed to find search result rows on Rossko.ru")
        await context.page.screenshot(path="rossko_no_rows_debug.png")
        return

    context.log.info(f"Found {len(item_links)} matches on Rossko.ru")
    requests_to_add = []
    for link in item_links:
        # Extract Brand — use first text node only, not inner_text which includes children
        brand_el = await link.query_selector('[class*="brand__"]')
        brand_raw = (await brand_el.inner_text()).strip() if brand_el else ""
        # Take only the first line before any newline (brand name)
        brand = brand_raw.split("\n")[0].strip() if brand_raw else "Unknown"

        # Extract Article/Part Number
        art_el = await link.query_selector('[class*="articleNumbers__"]')
        matched_article_raw = (await art_el.inner_text()).strip() if art_el else ""
        matched_article = matched_article_raw.split("\n")[0].strip() if matched_article_raw else ""

        # Extract Description/Name
        full_text = (await link.inner_text()).strip()
        # Normalize whitespace but keep words separated
        full_text = re.sub(r'\s+', ' ', full_text)
        
        # Extract Price from dedicated price element (not surrounding text)
        price_raw = ""
        price_el = await link.query_selector('[class*="priceWrapper__"], [class*="price__"]')
        if price_el:
            price_raw = (await price_el.inner_text()).strip()
        price = clean_price(price_raw)

        card_url = resolve_rossko_card_url(await link.get_attribute("href"), url)
        if price == "——" or not card_url:
            if not card_url:
                context.log.warning("Rossko result has no internal product-card URL; skipping evidence capture")
            continue
        # Subtract brand and article from full text to get description
        description = full_text
        if brand:
            description = description.replace(brand, "", 1).strip()
        if matched_article:
            description = description.replace(matched_article, "", 1).strip()
        # Clean up description — remove price leftovers, delivery hints
        description = re.sub(r'~?\d+\s+\S+.*$', '', description).strip()  # "~10 июля, пт"
        description = re.sub(r'Партнёрский склад.*$', '', description).strip()
        description = re.sub(r'\s+', ' ', description).strip()

        # Extract delivery / stock info
        delivery_el = await link.query_selector('[class*="delivery__"], [class*="deliver__"]')
        delivery = (await delivery_el.inner_text()).strip().replace("\n", " ") if delivery_el else "In stock"
        delivery = re.sub(r'\s+', ' ', delivery).strip()

        requests_to_add.append(Request.from_url(
            url=card_url,
            label="rossko_card",
            user_data={
                "article": article,
                "matched_article": matched_article,
                "brand": brand if brand != "Unknown" else "—",
                "description": description,
                "delivery": delivery,
                "price": price,
            },
        ))

    if requests_to_add:
        await context.add_requests(requests_to_add)


@router.handler('rossko_card')
async def handle_rossko_card(context: PlaywrightCrawlingContext) -> None:
    """Attach evidence from a Rossko internal product card, never from search results."""
    article = context.request.user_data.get('article', '')
    await context.page.wait_for_timeout(3000)
    consent = context.page.get_by_text("Согласен", exact=True)
    if await consent.count():
        await consent.first.click()
        await context.page.wait_for_timeout(1000)
    title = await context.page.title()
    price_node_count = await context.page.locator('[class*="price"]').count()
    if not rossko_card_has_product_data(title, price_node_count):
        context.log.warning(f"Rossko product card did not render product data: {context.request.url}")
        await context.page.screenshot(path="rossko_card_not_rendered_debug.png", full_page=True)
        return

    evidence = await capture_price_evidence(context, "rossko_ru", article)
    await context.push_data({
        "site": "rossko.ru",
        "search_article": article,
        "brand": context.request.user_data.get("brand", "—"),
        "article": context.request.user_data.get("matched_article", article),
        "description": context.request.user_data.get("description", ""),
        "delivery": context.request.user_data.get("delivery", "Unknown"),
        "price": context.request.user_data.get("price", "——"),
        **evidence,
    })

@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Default handler for unrecognized pages."""
    context.log.info(f'Processing default handler for URL: {context.request.url}...')
    await context.page.screenshot(path="default_handler_fallback.png")
