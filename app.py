import os
import random
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
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(c for c in str(value) if c.isdigit())
    return int(digits) if digits else None

def get_amazon_prices(query, max_results=5):
    """Fetch multiple Amazon.in results using Rainforest API"""
    if not RAINFOREST_API_KEY:
        return []

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
        print(f"Amazon API results found: {len(results)}")  # debug
        items = []

        for result in results[:max_results]:
            price = _parse_price(result.get("price", {}).get("raw"))
            items.append({
                "store": "Amazon",
                "title": result.get("title"),
                "price": price,
                "shipping": "See on Amazon",
                "status": "In Stock" if price else "Price unavailable",
                "url": result.get("link") or "https://www.amazon.in",
            })
        return items
    except Exception as e:
        print("Amazon error:", e)
        return []

def placeholder_flipkart_demo_multiple(amazon_items, min_items=5):
    """Return demo Flipkart items close to Amazon prices.
       Fill items up to min_items for demo purposes."""
    flipkart_items = []

    # simulate one Flipkart item per Amazon item
    for item in amazon_items:
        price = item.get("price")
        variation = random.uniform(-0.05, 0.05) if price else None
        flipkart_price = int(price * (1 + variation)) if price else None

        search_query = item.get("title", "product")
        search_url = f"https://www.flipkart.com/search?q={search_query.replace(' ', '+')}"

        flipkart_items.append({
            "store": "Flipkart",
            "title": search_query,
            "price": flipkart_price,
            "shipping": "See on Flipkart",
            "status": "In Stock" if flipkart_price else "Price unavailable",
            "url": search_url,
        })

    # fill additional demo items if Amazon returned less than min_items
    while len(flipkart_items) + len(amazon_items) < min_items:
        fake_title = f"{query} Item {len(flipkart_items)+1}"
        fake_price = int(random.uniform(500, 5000))  # random demo price
        search_url = f"https://www.flipkart.com/search?q={fake_title.replace(' ', '+')}"
        flipkart_items.append({
            "store": "Flipkart",
            "title": fake_title,
            "price": fake_price,
            "shipping": "See on Flipkart",
            "status": "In Stock",
            "url": search_url,
        })

    return flipkart_items

# --------------------
# API ENDPOINT
# --------------------
@app.route("/api/prices")
def api_prices():
    global query
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query required", "prices": []}), 400

    amazon_items = get_amazon_prices(query, max_results=3)  # fetch top 3 Amazon items
    flipkart_items = placeholder_flipkart_demo_multiple(amazon_items, min_items=5)

    all_items = amazon_items + flipkart_items

    # mark best price across all items
    valid_prices = [p["price"] for p in all_items if p.get("price") is not None]
    if valid_prices:
        best_price = min(valid_prices)
        for p in all_items:
            p["best"] = p.get("price") == best_price
    else:
        for p in all_items:
            p["best"] = False

    return jsonify({"query": query, "prices": all_items})

# --------------------
if __name__ == "__main__":
    app.run(debug=True)






