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
# EASY PARSER CONFIG
# --------------------
EASYPARSER_API_KEY = os.getenv("EASYPARSER_API_KEY")
EASYPARSER_DOMAIN = os.getenv("EASYPARSER_DOMAIN", ".com")  # IMPORTANT: .in is failing in your logs

# --------------------
# PRICE HELPERS
# --------------------
def _parse_price(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(c for c in str(value) if c.isdigit())
    return int(digits) if digits else None

def get_amazon_price(query: str):
    """
    Uses Easyparser PRODUCT_LOOKUP with keyword (singular), matching Easyparser docs/examples.
    """
    if not EASYPARSER_API_KEY:
        print("EASYPARSER_API_KEY not set")
        return None

    try:
        params = {
            "api_key": EASYPARSER_API_KEY,
            "platform": "AMZ",
            "operation": "PRODUCT_LOOKUP",
            "keyword": query,              # keyword (singular)
            "domain": EASYPARSER_DOMAIN,   # use allowed value like ".com"
            "output": "json",
        }

        resp = requests.get(
            "https://realtime.easyparser.com/v1/request",
            params=params,
            timeout=20,
        )

        print("Easyparser PRODUCT_LOOKUP status:", resp.status_code)
        print("Easyparser domain:", EASYPARSER_DOMAIN)
        if resp.status_code != 200:
            print("Easyparser error response:", resp.text[:700])
            return None

        data = resp.json()

        # Debug (optional): print response structure
        print("=== Easyparser JSON (truncated) ===")
        print(json.dumps(data, indent=2)[:1200])
        print("=== END Easyparser JSON ===")

        result = data.get("result") or {}
        search_result = result.get("search_result") or {}
        products = search_result.get("products") or []

        if not products:
            print("No products for query:", query)
            return None

        first = products[0]
        asin = first.get("asin")
        url = first.get("url") or first.get("product_url") or (f"https://www.amazon.com/dp/{asin}" if asin else None)

        price_raw = None
        price_obj = first.get("price")
        if isinstance(price_obj, dict):
            price_raw = price_obj.get("raw") or price_obj.get("value") or price_obj.get("amount")
        elif price_obj is not None:
            price_raw = price_obj

        price = _parse_price(price_raw)

        return {
            "store": "Amazon",
            "price": price,
            "shipping": "See on Amazon",
            "status": "In Stock" if price else "Price unavailable",
            "url": url or "https://www.amazon.com",
        }

    except Exception as e:
        print("Amazon (Easyparser) error:", type(e).__name__, str(e))
        return None

def placeholder_flipkart_demo(amazon_price=None, query=None):
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
        return jsonify({"error": "query required", "prices": []}), 400

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
            p["best"] = (p.get("price") == best_price)
    else:
        for p in items:
            p["best"] = False

    return jsonify({"query": query, "prices": items})

if __name__ == "__main__":
    print("EASYPARSER_API_KEY set:", bool(EASYPARSER_API_KEY))
    print("EASYPARSER_DOMAIN:", EASYPARSER_DOMAIN)
    app.run(debug=True)

