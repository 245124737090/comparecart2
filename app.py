import random
import requests
from flask import Flask, render_template, jsonify, request
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ---------------- AMAZON (BEST EFFORT) ----------------
def get_amazon_price(query):
    try:
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        r = requests.get(url, headers=HEADERS, timeout=12)

        soup = BeautifulSoup(r.text, "lxml")
        product = soup.select_one("div[data-component-type='s-search-result']")
        if not product:
            return None

        price_whole = product.select_one(".a-price-whole")
        link = product.select_one("a.a-link-normal")
        if not price_whole or not link:
            return None

        price = int(re.sub(r"[^\d]", "", price_whole.text))

        return {
            "retailer": "Amazon",
            "price": price,
            "status": "In Stock",
            "shipping": "Standard",
            "url": "https://www.amazon.in" + link["href"],
            "estimated": False
        }
    except:
        return None

# ---------------- FALLBACK PRICE ----------------
def fallback_price(query):
    # realistic deterministic price
    return 25000 + (abs(hash(query)) % 75000)

# ---------------- FLIPKART ±5% ----------------
def get_flipkart_price(base_price, query):
    variation = random.uniform(-0.05, 0.05)
    price = int(base_price * (1 + variation))

    return {
        "retailer": "Flipkart",
        "price": price,
        "status": "In Stock",
        "shipping": "Standard",
        "url": f"https://www.flipkart.com/search?q={query.replace(' ', '+')}",
        "estimated": True
    }

# ---------------- API ----------------
@app.route("/api/prices")
def api_prices():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"prices": []})

    prices = []
    amazon = get_amazon_price(query)

    if amazon:
        base_price = amazon["price"]
        prices.append(amazon)
    else:
        base_price = fallback_price(query)
        prices.append({
            "retailer": "Amazon",
            "price": base_price,
            "status": "In Stock",
            "shipping": "Standard",
            "url": f"https://www.amazon.in/s?k={query.replace(' ', '+')}",
            "estimated": True
        })

    prices.append(get_flipkart_price(base_price, query))

    prices.sort(key=lambda x: x["price"])
    for i, p in enumerate(prices):
        p["best"] = i == 0

    return jsonify({"prices": prices})

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run()
