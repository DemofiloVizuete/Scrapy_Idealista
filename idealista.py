import asyncio
import json
import re
from typing import Dict, List
from collections import defaultdict 
from urllib.parse import urljoin
import httpx
from parsel import Selector
from typing_extensions import TypedDict

# Establish persisten HTTPX session with browser-like headers to avoid blocking
BASE_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-US;en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
}
session = httpx.AsyncClient(headers=BASE_HEADERS, follow_redirects=True)

# type hints fo expected results so we can visualize our scraper easier:
class PropertyResult(TypedDict):
    url: str
    title: str
    location: str
    price: int
    currency: str
    description: str
    updated: str
    features: Dict[str, List[str]]
    images: Dict[str, List[str]]
    plans: List[str]


def parse_property(response: httpx.Response) -> PropertyResult:
    """parse Idealista.com property page"""
    # load response's HTML tree for parsing:
    selector = Selector(text=response.text)
    css = lambda x: selector.css(x).get("").strip()
    css_all = lambda x: selector.css(x).getall()

    data = {}
    # Meta data
    data["url"] = str(response.url)

    # Basic information
    data['title'] = css("h1 .main-info__title-main::text")
    data['location'] = css(".main-info__title-minor::text")
    data['currency'] = css(".info-data-price::text")
    data['price'] = int(css(".info-data-price span::text").replace(".", ""))
    data['description'] = "\n".join(css_all("div.comment ::text")).strip()
    data["updated"] = selector.xpath("//p[@class='stats-text']""[contains(text(),'updated on')]/text()").get("").split(" on ")[-1]

    # Features
    data["features"] = {}
    #  first we extract each feature block like "Basic Features" or "Amenities"
    for feature_block in selector.css(".details-property-h2"):
        # then for each block we extract all bullet points underneath them
        label = feature_block.xpath("text()").get()
        features = feature_block.xpath("following-sibling::div[1]//li")
        data["features"][label] = [
            ''.join(feat.xpath(".//text()").getall()).strip()
            for feat in features
        ]

    # Images
    # the images are tucked away in a javascript variable.
    # We can use regular expressions to find the variable and parse it as a dictionary:
    image_data = re.findall(r"fullScreenGalleryPics\s*:\s*(\[.+?\]),", response.text)[0]
    
    # we also need to replace unquoted keys to quoted keys (i.e. title -> "title"):
    images = json.loads(re.sub(r'(\w+?):([^/])', r'"\1":\2', image_data))
    data['images'] = defaultdict(list)
    data['plans'] = []
    for image in images:
        url = urljoin(str(response.url), image['imageUrl'])
        if image['isPlan']:
            data['plans'].append(url)
        else:
            data['images'][image['tag']].append(url)
    return data


async def scrape_properties(urls: List[str]) -> List[PropertyResult]:
    """Scrape Idealista.com properties"""
    properties = []
    to_scrape = [session.get(url) for url in urls]
    # tip: asyncio.as_completed allows concurrent scraping - super fast!
    for response in asyncio.as_completed(to_scrape):
        response = await response
        print(response.status_code)
        if response.status_code != 200:
            print(f"can't scrape property: {response.url}")
            continue
        properties.append(parse_property(response))
    return properties    

def parse_province(response: httpx.Response) -> List[str]:
    """parse province page for area search urls"""
    selector = Selector(text=response.text)
    urls = selector.css("#location_list li>a::attr(href)").getall()
    return [urljoin(str(response.url), url) for url in urls]


async def scrape_provinces(urls: List[str]) -> List[str]:
    """
    Scrape province pages like:
    https://www.idealista.com/en/venta-viviendas/malaga-provincia/con-chalets/municipios
    for search page urls like:
    https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/
    """
    to_scrape = [session.get(url) for url in urls]
    search_urls = []
    for response_future in asyncio.as_completed(to_scrape):
        response = await response_future
        search_urls.extend(parse_province(response))
    return search_urls    

def parse_search(response: httpx.Response) -> List[str]:
    """Parse search result page for 30 listings"""
    selector = Selector(text=response.text)
    urls = selector.css("article.item .item-link::attr(href)").getall()
    return [urljoin(str(response.url), url) for url in urls]

async def scrape_search(url: str, paginate=True, max_pages: int = None) -> List[str]:
    """
    Scrape search urls like:
    https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/
    for proprety urls
    """
    first_page = await session.get(url)
    property_urls = parse_search(first_page)
    if not paginate:
        return property_urls
    total_results = first_page.selector.css("h1#h1-container").re(": (.+) houses")[0]
    total_pages = math.ceil(int(total_results.replace(",", "")) / 30)
    if total_pages > 60:
        print(f"search contains more than max page limit ({total_pages}/60)")
        total_pages = 60
    # scrape all available pages in the search if max_scrape_pages is None or max_scrape_pages > total_pages
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    else:
        total_pages = total_pages
    print(f"scraping {total_pages} of search results concurrently")
    to_scrape = [
        session.get(first_page.url + f"pagina-{page}.htm")
        for page in range(2, total_pages + 1)
    ]
    async for response in asyncio.as_completed(to_scrape):
        property_urls.extend(parse_search(await response))
    return property_urls  

