import asyncio
import json
from pathlib import Path
from idealista_search import *

if __name__ == "__main__":
    search_data = asyncio.run(scrape_search(
        url="https://www.idealista.com/venta-viviendas/sevilla/santa-justa-miraflores-cruz-roja/ctra-de-carmona-miraflores/",
        # remove the max_scrape_pages paremeter to scrape all pages
        max_scrape_pages=3
    ))
    
    with open("search_data.json", "w", encoding="utf-8") as file:
        json.dump(search_data, file, indent=2, ensure_ascii=False)