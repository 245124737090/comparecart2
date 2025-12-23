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

def _parse_price(value):
    """Convert '₹50,000' or similar to int 50000."""
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None

def _amazon_price(query):
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
            timeout=10,
        )
        data = resp.json()
        results = data.get("search_results") or []
        if not results:
            return None

        item = results[0]
        price_obj = item.get("price") or {}
        price = _parse_price(price_obj.get("raw") or price_obj.get("value"))

        return {
            "store": "Amazon",
            "price": price,
            "shipping": "See on Amazon",
            "status": "In Stock",
            "url": item.get("link") or "https://www.amazon.in",
        }
    except Exception as e:
        print("Amazon price error:", e)
        return None

def _flipkart_price(query):
    """Fetch first Flipkart result via public scraper API."""
    try:
        url = f"https://flipkart-scraper-api.vercel.app/search/{query}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        results = data.get("result") or data.get("results") or []
        if not results:
            return None

        item = results[0]
        price = _parse_price(item.get("current_price") or item.get("price"))

        return {
            "store": "Flipkart",
            "price": price,
            "shipping": "See on Flipkart",
            "status": "In Stock",
            "url": item.get("link") or item.get("query_url") or "https://www.flipkart.com",
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

    amazon = _amazon_price(query)
    flipkart = _flipkart_price(query)

    items = [p for p in [amazon, flipkart] if p]

    if not items:
        return jsonify({"query": query, "prices": []})

    # mark best (cheapest) price
    valid = [p for p in items if p.get("price") is not None]
    if valid:
        best_price = min(p["price"] for p in valid)
        for p in items:
            p["best"] = p.get("price") == best_price
    else:
        for p in items:
            p["best"] = False

    return jsonify({"query": query, "prices": items})

# --------------------
if __name__ == "__main__":
    app.run(debug=True)
