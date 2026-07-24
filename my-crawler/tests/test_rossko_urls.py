from my_crawler.routes import resolve_rossko_card_url, rossko_card_has_product_data


def test_resolve_rossko_card_url_accepts_relative_product_card():
    assert resolve_rossko_card_url(
        "/card/lynxauto-330l-nsin0018142251/?source=Techdoc&ref=catalog",
        "https://sochi.rossko.ru/search?q=330L",
    ) == "https://sochi.rossko.ru/card/lynxauto-330l-nsin0018142251/?source=Techdoc&ref=catalog"


def test_resolve_rossko_card_url_accepts_result_product_card():
    assert resolve_rossko_card_url(
        "/product?text=NSII0027852692&q=oc90&sid=session-id&sp=1&si=1&st=article",
        "https://sochi.rossko.ru/search?q=oc90",
    ) == "https://sochi.rossko.ru/product?text=NSII0027852692&q=oc90&sid=session-id&sp=1&si=1&st=article"


def test_resolve_rossko_card_url_rejects_search_or_foreign_urls():
    base_url = "https://sochi.rossko.ru/search?q=330L"
    assert resolve_rossko_card_url("/search?q=330L", base_url) is None
    assert resolve_rossko_card_url("https://example.com/card/330L", base_url) is None


def test_rossko_card_requires_rendered_price_nodes():
    assert rossko_card_has_product_data("Росско — Карточка продукта", 1)
    assert not rossko_card_has_product_data("Росско — Карточка продукта", 0)
    assert not rossko_card_has_product_data("", 4)
