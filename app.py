import random
import requests
import os
import re
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Get free API key from https://www.scraperapi.com/
SCRAPERAPI_API_KEY = os.getenv('SCRAPERAPI_API_KEY')  # Set this env var
if not SCRAPERAPI_API_KEY:
    raise ValueError("Set SCRAPERAPI_API_KEY environment variable")

def get_amazon_price(query):
    """Fetch real Amazon.in price using ScraperAPI Amazon Search."""
    try:
        url = "https://api.scraperapi.com/structured/amazon/search"
        params = {
            'api_key': SCRAPERAPI_API_KEY,
            'query': query,
            'country': 'in',
            'tld': 'in',
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        
        if 'results' in data and data['results']:
            first_product = data['results'][0]
            price = first_product.get('price')
            if isinstance(price, (int, float)):
                price = int(price)
            else:
                # Fallback parse if string
                price_match = re.search(r'[\d,]+', str(price))
                price = int(price_match.group().replace(',', '')) if price_match else None
            if price:
                link = first_product.get('link', f"https://www.amazon.in/s?k={query.replace(' ', '+')}")
                availability = first_product.get('availability', 'In Stock')
                return {
                    "retailer": "Amazon",
                    "price": price,
                    "status": availability,
                    "shipping": "Standard",
                    "url": link,
                    "estimated": False
                }
        return None
    except Exception as e:
        print(f"ScraperAPI error: {e}")
        return None

def fallback_price(query):
    """Deterministic fallback."""
    return 25000 + (abs(hash(query)) % 75000)

def get_flipkart_price(base_price, query):
    """Flipkart ±5% of Amazon base."""
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
    app.run(debug=True)

