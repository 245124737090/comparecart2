import os
import requests
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
# PRICE HELPERS
# --------------------
RAINFOREST_API_KEY = os.getenv("RAINFOREST_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "flipkart1.p.rapidapi.com"  # RapidAPI host

def _parse_price(value):
    """Convert price like '₹99,999' or 99999 to int."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(c for c in str(value) if c.isdigit())
    return int(digits) if digits else None

def get_amazon_price(query):
    """Fetch first Amazon.in result using Rainforest API."""
    if not RAINFOREST_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.rainforestapi.com/request",
            params={
                "api_key": RAINFOREST_API_KEY,
                "type": "search",
                "amazon_domain": "amazon.in",
                "search_term": query,
                "sort_by": "featured"
            },
            timeout=10
        )
        data = resp.json()
        results = data.get("search_results") or []
        if not results:
            return None
        first = results[0]
        price = _parse_price(first.get("price", {}).get("raw"))
        return {
            "store": "Amazon",
            "price": price,
            "shipping": "See on Amazon",
            "status": "In Stock",
            "url": first.get("link") or "https://www.amazon.in",
        }
    except Exception as e:
        print("Amazon price error:", e)
        return None

def get_flipkart_price(query):
    """Fetch first Flipkart result using RapidAPI scraper."""
    if not RAPIDAPI_KEY:
        return None
    try:
        url = f"https://flipkart1.p.rapidapi.com/search/autocomplete?query={query}"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        products = data.get("products") or []
        if not products:
            return None
        first = products[0]
        price = _parse_price(first.get("price", {}).get("value"))
        return {
            "store": "Flipkart",
            "price": price,
            "shipping": "See on Flipkart",
            "status": "In Stock",
            "url": first.get("url") or "https://www.flipkart.com",
        }
    except Exception as e:
        print("Flipkart price error:", e)
        return None

# --------------------
# API ENDPOINT
# --------------------
@app.route("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query required", "prices": []}), 400

    amazon = get_amazon_price(query)
    flipkart = get_flipkart_price(query)

    items = [p for p in [amazon, flipkart] if p]

    if not items:
        return jsonify({"query": query, "prices": []})

    # mark best price
    valid_prices = [p["price"] for p in items if p.get("price") is not None]
    if valid_prices:
        best_price = min(valid_prices)
        for p in items:
            p["best"] = p["price"] == best_price
    else:
        for p in items:
            p["best"] = False

    return jsonify({"query": query, "prices": items})

# --------------------
if __name__ == "__main__":
    app.run(debug=True)


