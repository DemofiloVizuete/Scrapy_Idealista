import asyncio
import json
from pathlib import Path
from idealista import *

output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)

"""
async def run():
    urls = ["https://www.idealista.com/inmueble/105235805/"]
    data = await scrape_properties(urls)
    print(json.dumps(data, indent=2, ensure_ascii=False))
"""

async def run():
    urls = ["https://www.idealista.com/venta-viviendas/sevilla/santa-justa-miraflores-cruz-roja/"]
    data = await scrape_provinces(urls)
    print(json.dumps(data, indent=2))

"""
async def run():
    data = await scrape_search(url="https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/",max_pages=1)
    print(json.dumps(data, indent=2))
"""

if __name__ == "__main__":
    asyncio.run(run())