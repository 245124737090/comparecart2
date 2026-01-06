import os
import requests
from flask import Flask, jsonify, request, render_template
from bs4 import BeautifulSoup

app = Flask(__name__)

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

def scrape(url):
    api = "https://api.scraperapi.com/"
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "country_code": "in"
    }
    r = requests.get(api, params=params, timeout=30)
    r.raise_for_status()
    return r.text

def amazon_price(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    html = scrape(url)
    soup = BeautifulSoup(html, "html.parser")

    price = soup.select_one("span.a-price-whole")
    if not price:
        return None

    return {
        "retailer": "Amazon",
        "price": int(price.text.replace(",", "").strip()),
        "status": "In Stock",
        "url": url
    }

def flipkart_price(query):
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    html = scrape(url)
    soup = BeautifulSoup(html, "html.parser")

    price = soup.select_one("div._30jeq3")
    if not price:
        return None

    return {
        "retailer": "Flipkart",
        "price": int(price.text.replace("₹", "").replace(",", "").strip()),
        "status": "In Stock",
        "url": url
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def prices():
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "query required"}), 400

    results = []
    for fn in (amazon_price, flipkart_price):
        data = fn(query)
        if data:
            results.append(data)

    best = min((p["price"] for p in results), default=None)
    for p in results:
        p["best"] = p["price"] == best

    return jsonify({
        "product": query,
        "prices": results
    })

if __name__ == "__main__":
    app.run(debug=True)

