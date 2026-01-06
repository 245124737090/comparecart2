import os
import random
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# --------------------
# AUTH
# --------------------
users = {}

@app.route("/")
def home():
    return render_template("index.html", user_email=session.get("user_email"))

@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    if not email or not password:
        flash("Email and password required")
        return redirect(url_for("home"))
    if email in users:
        flash("User already exists")
        return redirect(url_for("home"))
    users[email] = {"password_hash": generate_password_hash(password)}
    session["user_email"] = email
    flash("Signed up successfully")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    user = users.get(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid credentials")
        return redirect(url_for("home"))
    session["user_email"] = email
    flash("Logged in")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    flash("Logged out")
    return redirect(url_for("home"))

# --------------------
# PRICE HELPERS (EASYPARSER with DEBUG LOGS)
# --------------------
EASYPARSER_API_KEY = os.getenv("EASYPARSER_API_KEY")

def _parse_price(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(c for c in str(value) if c.isdigit())
    return int(digits) if digits else None

def get_amazon_price(query: str):
    """
    Updated Easyparser call with debugging to see exact response.
    """
    if not EASYPARSER_API_KEY:
        print("❌ EASYPARSER_API_KEY not set")
        return None

    try:
        # Try SEARCH first (most common)
        params = {
            "api_key": EASYPARSER_API_KEY,
            "platform": "AMZ",
            "operation": "SEARCH",
            "keywords": query,
            "domain": ".in",
            "output": "json",
            "page": "1"
        }
        
        resp = requests.get(
            "https://realtime.easyparser.com/v1/request",
            params=params,
            timeout=20,
        )
        
        print(f"🔍 Easyparser SEARCH status: {resp.status_code}")
        print(f"📊 Query: {query}")
        
        if resp.status_code != 200:
            print(f"❌ Easyparser error response: {resp.text[:500]}")
            return None

        data = resp.json()
        
        # DEBUG: Print full JSON response (truncated)
        print("=== EASYPARSER JSON START ===")
        print(json.dumps(data, indent=2)[:2000])
        print("=== EASYPARSER JSON END ===")
        print("=== KEYS in data ===")
        print(list(data.keys()))
        print("=== KEYS in data.get('result') ===")
        print(list(data.get('result', {}).keys()) if data.get('result') else "no result")
        print("=== END KEYS ===")

        # Try multiple common paths for products
        products = []
        if data.get('result'):
            result = data['result']
            products = (
                result.get('search_result', {}).get('products') or
                result.get('products') or
                result.get('items') or
                result.get('results') or
                []
            )
        elif data.get('products'):
            products = data['products']
        elif data.get('items'):
            products = data['items']
        elif data.get('results'):
            products = data['results']

        print(f"📦 Found {len(products)} products")

        if not products:
            print("❌ No products found")
            return None

        first = products[0]
        print(f"🔑 First product keys: {list(first.keys())}")

        asin = first.get("asin")
        product_url = first.get("url") or first.get("product_url")
        price_raw = None

        # Try multiple price paths
        price_obj = first.get("price")
        if isinstance(price_obj, dict):
            price_raw = price_obj.get("raw") or price_obj.get("value") or price_obj.get("amount")
        elif price_obj:
            price_raw = price_obj

        price = _parse_price(price_raw)
        print(f"💰 Price raw: '{price_raw}' -> parsed: {price}")

        if not product_url and asin:
            product_url = f"https://www.amazon.in/dp/{asin}"

        result = {
            "store": "Amazon",
            "price": price,
            "shipping": "See on Amazon",
            "status": "In Stock" if price else "Price unavailable",
            "url": product_url or "https://www.amazon.in",
        }
        print(f"✅ Amazon result: {result}")
        return result

    except requests.exceptions.Timeout:
        print("⏰ Easyparser timeout")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Response text: {resp.text[:300]}")
        return None
    except Exception as e:
        print(f"💥 Unexpected error: {type(e).__name__}: {e}")
        return None

def placeholder_flipkart_demo(amazon_price=None, query=None):
    """Demo Flipkart price near Amazon + search link."""
    if amazon_price:
        variation = random.uniform(-0.05, 0.05)
        flipkart_price = int(amazon_price * (1 + variation))
    else:
        flipkart_price = None

    search_url = (
        f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        if query
        else "https://www.flipkart.com"
    )
    return {
        "store": "Flipkart",
        "price": flipkart_price,
        "shipping": "See on Flipkart",
        "status": "In Stock" if flipkart_price else "Price unavailable",
        "url": search_url,
    }

# --------------------
# API ENDPOINT
# --------------------
@app.route("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        print("❌ No query parameter")
        return jsonify({"error": "query required", "prices": []}), 400

    print(f"🌐 /api/prices called with query: '{query}'")

    amazon = get_amazon_price(query)
    flipkart = placeholder_flipkart_demo(
        amazon_price=amazon.get("price") if amazon else None,
        query=query,
    )

    items = [p for p in [amazon, flipkart] if p]

    valid_prices = [p["price"] for p in items if p.get("price") is not None]
    if valid_prices:
        best_price = min(valid_prices)
        for p in items:
            p["best"] = p.get("price") == best_price
    else:
        for p in items:
            p["best"] = False

    print(f"📤 Returning {len(items)} prices: {items}")
    return jsonify({"query": query, "prices": items})

# --------------------
if __name__ == "__main__":
    print("🚀 Starting CompareCart Flask app")
    print(f"EASYPARSER_API_KEY is set: {'✅ YES' if EASYPARSER_API_KEY else '❌ NO'}")
    app.run(debug=True)


