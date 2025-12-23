import requests
from bs4 import BeautifulSoup

def amazon_price(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    price = soup.select_one(".a-price-whole")
    price = int(price.text.replace(",", "")) if price else 999999

    return {
        "store": "Amazon",
        "price": price,
        "status": "In Stock",
        "shipping": "Free",
        "url": url,
        "best": False
    }
