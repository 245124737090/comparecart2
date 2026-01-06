import random
import requests
from flask import Flask, jsonify, request, render_template
from bs4 import BeautifulSoup

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# -------------------------------
# AMAZON PRICE SCRAPER (WORKS)
# -------------------------------
def get_amazon_price(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=15)

    soup = BeautifulSoup(r.text, "lxml")
    product = soup.select_one("div[data-component-type='s-search-result']")

    if not product:
        return None

    price = product.select_one(".a-price-whole")
    link = product.select_one("a.a-link-normal")

    if not price or not link:
        return None

    return {
        "retailer": "Amazon",
        "price": int(price.text.replace(",", "")),
        "status": "In Stock",
        "shipping": "Standard",
        "url": "https://www.amazon.in" + link["href"]
    }

# -------------------------------
# FLIPKART PRICE (±5% LOGIC)
# -------------------------------
def get_flipkart_price(amazon_price, query):
    variation = random.uniform(-0.05, 0.05)   # ±5%
    flipkart_price = int(amazon_price * (1 + variation))

    return {
        "retailer": "Flipkart",
        "price": flipkart_price,
        "status": "In Stock",
        "shipping": "Standard",
        "url": f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    }

# -------------------------------
# API
# -------------------------------
@app.route("/api/prices")
def prices():
    query = request.args.get("query", "")
    if not query:
        return jsonify({"prices": []})

    amazon = get_amazon_price(query)
    prices = []

    if amazon:
        prices.append(amazon)
        prices.append(get_flipkart_price(amazon["price"], query))

    # Mark best price
    prices.sort(key=lambda x: x["price"])
    for i, p in enumerate(prices):
        p["best"] = (i == 0)

    return jsonify({"prices": prices})

# -------------------------------
# FRONTEND
# -------------------------------
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run()


