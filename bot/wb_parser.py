import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v7/search"
WB_CARD_URL = "https://www.wildberries.ru/catalog/{}/detail.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


def _get_proxy() -> Optional[str]:
    """Return proxy URL if PROXY_URL env var is set."""
    return os.environ.get("PROXY_URL")


def _extract_price(product: dict) -> Optional[int]:
    """Extract final price in rubles from product data."""
    try:
        sizes = product.get("sizes", [])
        for size in sizes:
            price_data = size.get("price", {})
            total = price_data.get("total")
            if total:
                return total // 100  # price comes in kopecks
    except Exception:
        pass
    return None


async def fetch_top_prices(query: str, top_n: int = 5) -> list[dict]:
    """
    Fetch top N cheapest products from Wildberries for a given query.

    Returns list of dicts: {name, price, article, url, brand}
    """
    params = {
        "query": query,
        "resultset": "catalog",
        "limit": 100,
        "sort": "priceup",
        "page": 1,
        "dest": -1257786,  # Moscow region destination for correct prices
    }

    proxy = _get_proxy()
    if proxy:
        logger.info(f"Using proxy: {proxy.split('@')[-1]}")  # log host only, not credentials

    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=15.0,
            proxy=proxy,
        ) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching WB data: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching WB data: {e}")
        raise

    products = data.get("data", {}).get("products", [])
    if not products:
        logger.warning(f"No products found for query: {query}")
        return []

    results = []
    for product in products:
        price = _extract_price(product)
        if price is None:
            continue

        article = product.get("id")
        name = product.get("name", "").strip()
        brand = product.get("brand", "").strip()

        results.append({
            "name": name,
            "brand": brand,
            "price": price,
            "article": article,
            "url": WB_CARD_URL.format(article),
        })

    # Sort by price ascending, return top N
    results.sort(key=lambda x: x["price"])
    return results[:top_n]
