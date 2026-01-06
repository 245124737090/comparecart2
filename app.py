import os
import random
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# ====================
# AUTH (demo in-memory)
# ====================
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

# ====================
# EASY PARSER CONFIG
# ====================
EASYPARSER_API_KEY = os.getenv("EASYPARSER_API_KEY")
# IMPORTANT: your logs showed .in was rejected; use an allowed domain like ".com"
EASYPARSER_DOMAIN = os.getenv("EASYPARSER_DOMAIN", ".com")
EASYPARSER_TIMEOUT = int(os.getenv("EASYPARSER_TIMEOUT", "25"))

EASYPARSER_ENDPOINT = "https://realtime.easyparser.com/v1/request"

# ====================
# HELPERS
# ====================
def _parse_price(value):
    if value is None or value == "":
        return None

    # number
    if isinstance(value, (int, float)):
        try:
            return int(float(value))
        except Exception:
            return None

    # dict: try common keys
    if isinstance(value, dict):
        for k in ("raw", "value", "amount", "price", "current_price", "price_value"):
            if k in value and value[k] not in (None, ""):
                return _parse_price(value[k])
        return None

    # string like "$1,299.99" or "₹ 99,999"
    s = str(value)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None

def _easyparser_get(operation: str, **payload):
    if not EASYPARSER_API_KEY:
        raise RuntimeError("EASYPARSER_API_KEY not set")

    params = {
        "api_key": EASYPARSER_API_KEY,
        "platform": "AMZ",
        "operation": operation,
        "domain": EASYPARSER_DOMAIN,
        "output": "json",
    }
    params.update(payload)

    resp = requests.get(EASYPARSER_ENDPOINT, params=params, timeout=EASYPARSER_TIMEOUT)
    try:
        data = resp.json()
    except Exception:
        data = None
    return resp.status_code, data, resp.text

def _pick_first_product(product_lookup_json):
    result = (product_lookup_json or {}).get("result") or {}
    search_result = result.get("search_result") or {}
    products = search_result.get("products") or []
    return products[0] if products else None

def _extract_url_from_product(prod: dict):
    if not isinstance(prod, dict):
        return None
    # Your Easyparser response shows "link" (important)
    return prod.get("link") or prod.get("url") or prod.get("product_url")

def _extract_price_from_product(prod: dict):
    if not isinstance(prod, dict):
        return None

    # Common price shapes
    if "price" in prod:
        p = _parse_price(prod.get("price"))
        if p is not None:
            return p

    # Extra fallbacks (sometimes APIs use these)
    for k in ("current_price", "sale_price", "deal_price", "price_string", "price_raw"):
        if k in prod:
            p = _parse_price(prod.get(k))
            if p is not None:
                return p

    return None

def _extract_price_from_detail(detail_json: dict):
    if not isinstance(detail_json, dict):
        return None

    # Sometimes there is a direct "price"
    if "price" in detail_json:
        p = _parse_price(detail_json.get("price"))
        if p is not None:
            return p

    # Often offers contain numeric price
    offers = detail_json.get("offers") or []
    if isinstance(offers, list) and offers:
        first_offer = offers[0] if isinstance(offers[0], dict) else None
        if first_offer:
            if "price" in first_offer:
                p = _parse_price(first_offer.get("price"))
                if p is not None:
                    return p
            # sometimes nested
            if isinstance(first_offer.get("price"), dict):
                p = _parse_price(first_offer.get("price"))
                if p is not None:
                    return p

    return None

# ====================
# PRICE FETCHERS
# ====================
def get_amazon_price(query: str):
    """
    1) PRODUCT_LOOKUP keyword -> get first product, ASIN + link
    2) Try price from lookup product
    3) If missing, call DETAIL asin -> try price from detail/offers
    """
    try:
        status, data, text = _easyparser_get("PRODUCT_LOOKUP", keyword=query)
        print("Easyparser PRODUCT_LOOKUP status:", status, "domain:", EASYPARSER_DOMAIN)
        if status != 200:
            print("Easyparser PRODUCT_LOOKUP error:", text[:800])
            return None

        first = _pick_first_product(data)
        if not first:
            print("Easyparser: no products for query:", query)
            return None

        asin = first.get("asin")
        url = _extract_url_from_product(first)
        price = _extract_price_from_product(first)

        # If lookup didn’t include price, try DETAIL (more reliable)
        if price is None and asin:
            d_status, d_data, d_text = _easyparser_get("DETAIL", asin=asin)
            print("Easyparser DETAIL status:", d_status, "asin:", asin)
            if d_status == 200 and isinstance(d_data, dict):
                price = _extract_price_from_detail(d_data)
                url = url or d_data.get("url") or d_data.get("product_url")
            else:
                print("Easyparser DETAIL error:", d_text[:800])

        # Final fallback URL
        if not url and asin:
            url = f"https://www.amazon.com/dp/{asin}"

        # If still no price, return None (frontend stays stable because Flipkart demo returns a number)
        if price is None:
            print("Easyparser: price not found for:", query, "asin:", asin)
            return None

        return {
            "store": "Amazon",
            "price": int(price),
            "shipping": "See on Amazon",
            "status": "In Stock",
            "url": url or "https://www.amazon.com",
        }

    except Exception as e:
        print("Amazon (Easyparser) error:", type(e).__name__, str(e))
        return None

def placeholder_flipkart_demo(amazon_price=None, query=None):
    """
    Always returns a numeric demo price so the frontend never crashes.
    """
    if amazon_price:
        variation = random.uniform(-0.05, 0.05)  # ±5%
        flipkart_price = int(amazon_price * (1 + variation))
    else:
        # deterministic fallback based on query text (so it doesn't jump every refresh)
        base = 10000 + (abs(hash(query or "")) % 90000)
        flipkart_price = int(base)

    search_url = (
        f"https://www.flipkart.com/search?q={(query or '').replace(' ', '+')}"
        if query
        else "https://www.flipkart.com"
    )
    return {
        "store": "Flipkart",
        "price": flipkart_price,
        "shipping": "See on Flipkart",
        "status": "In Stock",
        "url": search_url,
    }

# ====================
# API ENDPOINT
# ====================
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

    items = [p for p in (amazon, flipkart) if p]

    # mark best price
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
