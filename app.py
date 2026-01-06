import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
TIMEOUT = 30

def scrape_page(url):
    api_url = "https://api.scraperapi.com/"
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "country_code": "in",
        "render": "false"
    }
    r = requests.get(api_url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def extract_price(html):
    import re
    prices = re.findall(r"₹\s?[\d,]+", html)
    if prices:
        return int(prices[0].replace("₹", "").replace(",", ""))
    return None

# ---------------- AMAZON ----------------
def get_amazon_price(query):
    try:
        search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        html = scrape_page(search_url)
        price = extract_price(html)
        if not price:
            return None
        return {
            "store": "Amazon",
            "price": price,
            "url": search_url,
            "status": "In Stock"
        }
    except Exception as e:
        print("Amazon error:", e)
        return None

# ---------------- FLIPKART ----------------
def get_flipkart_price(query):
    try:
        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        html = scrape_page(search_url)
        price = extract_price(html)
        if not price:
            return None
        return {
            "store": "Flipkart",
            "price": price,
            "url": search_url,
            "status": "In Stock"
        }
    except Exception as e:
        print("Flipkart error:", e)
        return None

# ---------------- API ----------------
@app.route("/api/prices")
def api_prices():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400

    amazon = get_amazon_price(query)
    flipkart = get_flipkart_price(query)

    prices = [p for p in (amazon, flipkart) if p]

    if prices:
        best = min(p["price"] for p in prices)
        for p in prices:
            p["best"] = (p["price"] == best)

    return jsonify({
        "query": query,
        "prices": prices
    })

if __name__ == "__main__":
    app.run()
