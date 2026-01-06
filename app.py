import requests
from flask import Flask, render_template, jsonify, request
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ---------------- AMAZON SCRAPER ----------------
def get_amazon_price(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=15)

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    product = soup.select_one("div[data-component-type='s-search-result']")
    if not product:
        return None

    price_whole = product.select_one(".a-price-whole")
    price_frac = product.select_one(".a-price-fraction")
    link = product.select_one("a.a-link-normal")

    if not price_whole:
        return None

    price = price_whole.text.replace(",", "")
    if price_frac:
        price += price_frac.text

    return {
        "retailer": "Amazon",
        "price": int(re.sub(r"[^\d]", "", price)),
        "status": "In Stock",
        "shipping": "Standard",
        "url": "https://www.amazon.in" + link["href"]
    }

# ---------------- FLIPKART SCRAPER ----------------
def get_flipkart_price(query):
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=15)

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    product = soup.select_one("div._1AtVbE")
    price_tag = soup.select_one("div._30jeq3")
    link = soup.select_one("a._1fQZEK")

    if not price_tag or not link:
        return None

    price = price_tag.text.replace("₹", "").replace(",", "")

    return {
        "retailer": "Flipkart",
        "price": int(price),
        "status": "In Stock",
        "shipping": "Standard",
        "url": "https://www.flipkart.com" + link["href"]
    }

# ---------------- API ----------------
@app.route("/api/prices")
def api_prices():
    query = request.args.get("query")
    if not query:
        return jsonify({"prices": []})

    prices = []
    amazon = get_amazon_price(query)
    flipkart = get_flipkart_price(query)

    if amazon:
        prices.append(amazon)
    if flipkart:
        prices.append(flipkart)

    prices.sort(key=lambda x: x["price"])
    for i, p in enumerate(prices):
        p["best"] = i == 0

    return jsonify({"prices": prices})

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run()



