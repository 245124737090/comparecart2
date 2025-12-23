# Example Flask route (replace your current /api/prices)
import os, requests
from flask import Flask, request, jsonify

app = Flask(__name__)
RAINFOREST_API_KEY = os.getenv("RAINFOREST_API_KEY")

def parse_price(v):
    if isinstance(v, (int, float)):
        return v
    if not v:
        return None
    return int("".join(ch for ch in str(v) if ch.isdigit()) or 0)

def amazon_price(query):
    try:
        r = requests.get(
            "https://api.rainforestapi.com/request",
            params={
                "api_key": RAINFOREST_API_KEY,
                "type": "search",
                "amazon_domain": "amazon.in",
                "search_term": query,
                "sort_by": "featured",
            },
            timeout=10,
        )
        data = r.json()
        item = (data.get("search_results") or [None])[0]
        if not item:
            return None
        p = item.get("price", {})
        price = parse_price(p.get("raw") or p.get("value"))
        return {
            "store": "Amazon",
            "price": price,
            "url": item.get("link") or "https://www.amazon.in",
            "status": "In Stock",
            "shipping": "See on Amazon",
        }
    except Exception:
        return None

def flipkart_price(query):
    try:
        r = requests.get(
            f"https://flipkart-scraper-api.vercel.app/search/{query}",
            timeout=10,
        )
        data = r.json()
        item = (data.get("result") or data.get("results") or [None])[0]
        if not item:
            return None
        price = parse_price(item.get("current_price") or item.get("price"))
        return {
            "store": "Flipkart",
            "price": price,
            "url": item.get("link") or item.get("query_url") or "https://www.flipkart.com",
            "status": "In Stock",
            "shipping": "See on Flipkart",
        }
    except Exception:
        return None

@app.get("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"prices": [], "query": query})

    amz = amazon_price(query)
    flp = flipkart_price(query)
    items = [x for x in [flp, amz] if x]

    if not items:
        return jsonify({"prices": [], "query": query})

    valid = [i for i in items if i["price"] is not None]
    if valid:
        best_price = min(i["price"] for i in valid)
        for i in items:
            i["best"] = i["price"] == best_price
    else:
        for i in items:
            i["best"] = False

    return jsonify({"prices": items, "query": query})

