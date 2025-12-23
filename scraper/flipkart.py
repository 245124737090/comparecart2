import requests
from bs4 import BeautifulSoup

def flipkart_price(query):
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    price = soup.select_one("._30jeq3")
    price = int(price.text.replace("₹","").replace(",","")) if price else 999999

    return {
        "store": "Flipkart",
        "price": price,
        "status": "In Stock",
        "shipping": "Standard",
        "url": url,
        "best": False
    }
