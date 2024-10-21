import json
import math
import httpx
import asyncio

from typing import Dict, List

# Establish persisten HTTPX session with browser-like headers to avoid blocking
BASE_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-US;en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
}

session = httpx.AsyncClient(headers=BASE_HEADERS, follow_redirects=True)


def parse_search_data(response) -> List[Dict]:
    """parse search result data"""
    selector = Selector(response.text)
    total_results = selector.css("h1#h1-container").re(": (.+) houses")[0]
    max_pages = math.ceil(int(total_results.replace(",", "")) / 30)
    max_pages = 60  if max_pages > 60 else max_pages
    search_data = []
    for box in selector.xpath("//section[contains(@class, 'items-list')]/article[contains(@class, 'item')]"):
        ad = box.xpath(".//p[@class='adv_txt']") # ignore ad listings
        if ad:
            continue
        price = box.xpath(".//span[contains(@class, 'item-price')]/text()").get()
        parking = box.xpath(".//span[@class='item-parking']").get()
        company_url = box.xpath(".//picture[@class='logo-branding']/a/@href").get()
        search_data.append({
            "title": box.xpath(".//div/a/@title").get(),
            "link": "https://www.idealista.com" + box.xpath(".//div/a/@href").get(),
            "picture": box.xpath(".//img/@src").get(),
            "price": int(price.replace(".", '')) if price else None,
            "currency": box.xpath(".//span[contains(@class, 'item-price')]/span/text()").get(),
            "parking_included": True if parking else False,
            "details": box.xpath(".//div[@class='item-detail-char']/span/text()").getall(),
            "description": box.xpath(".//div[contains(@class, 'item-description')]/p/text()").get().replace('\n', ''),
            "tags": box.xpath(".//div[@class='listing-tags-container']/span/text()").getall(),
            "listing_company": box.xpath(".//picture[@class='logo-branding']/a/@title").get(),
            "listing_company_url": "https://www.idealista.com" + company_url if company_url else None
        })
    return {"max_pages": max_pages, "search_data": search_data}


async def scrape_search(url: str, max_scrape_pages: int = None) -> List[Dict]:
    """scrape Idealista search results"""
    first_page = await session.get(url)
    assert first_page == 200, "request is blocked, use ScrapFly code tab"
    data = parse_search_data(first_page)
    search_data = data["search_data"]
    max_pages = data["max_pages"]

    # get the number of total pages to scrape
    if max_scrape_pages and max_scrape_pages < max_pages:
        max_pages = max_scrape_pages

    # scrape the remaining pages concurrently
    to_scrape = [
        session(url + f"pagina-{page}.htm")
        for page in range(2, max_pages + 1)
    ]
    print(f"scraping search pagination, {max_pages - 1} pages remaining")
    for response in asyncio.as_completed(to_scrape):
        search_data.extend(parse_search_data(await response)["search_data"])
    print(f"scraped {len(search_data)} property listings from search pages")
    return search_data