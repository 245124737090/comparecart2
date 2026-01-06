import os
import random
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

# ====================
# APP CONFIG
# ====================
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# ====================
# AUTH (Demo In-Memory)
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

    users[email] = {
        "password_hash": generate_password_hash(password)
    }
    session["user_email"] = email
    flash("Signup successful")
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
    flash("Logged in successfully")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    flash("Logged out")
    return redirect(url_for("home"))

# ====================
# OPENWEB NINJA CONFIG
# ====================
OPENWEBNINJA_API_KEY = os.getenv("OPENWEBNINJA_API_KEY")
OPENWEBNINJA_ENDPOINT = "https://api.openwebninja.com/v1/search"
TIMEOUT = 25

# ====================
# HELPERS
# ====================
def call_openwebninja(engine, query):
    if not OPENWEBNINJA_API_KEY:
        raise RuntimeError("OPENWEBNINJA_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {OPENWEBNINJA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "engine": engine,
        "query": query,
        "country": "in",
        "language": "en"
    }

    response = requests.post(
        OPENWEBNINJA_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()

# ====================
# AMAZON PRICE
# ====================
def get_amazon_price(query):
    try:
        data = call_openwebninja("amazon_search", query)
        products = data.get("products", [])

        if not products:
            return None

        p = products[0]
        price = p.get("price")

        if not price:
            return None

        return {
            "store": "Amazon",
            "price": int(price),
            "shipping": p.get("delivery", "See on Amazon"),
            "status": p.get("availability", "In Stock"),
            "url": p.get("link"),
        }

    except Exception as e:
        print("Amazon error:", e)
        return None

# ====================
# FLIPKART PRICE
# ====================
def get_flipkart_price(query):
    try:
        data = call_openwebninja("flipkart_search", query)
        products = data.get("products", [])

        if not products:
            return None

        p = products[0]
        price = p.get("price")

        if not price:
            return None

        return {
            "store": "Flipkart",
            "price": int(price),
            "shipping": p.get("delivery", "See on Flipkart"),
            "status": p.get("availability", "In Stock"),
            "url": p.get("link"),
        }

    except Exception as e:
        print("Flipkart error:", e)
        return None

# ====================
# API ENDPOINT
# ====================
@app.route("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query required", "prices": []}), 400

    amazon = get_amazon_price(query)
    flipkart = get_flipkart_price(query)

    items = [p for p in (amazon, flipkart) if p]

    if items:
        best_price = min(p["price"] for p in items)
        for p in items:
            p["best"] = (p["price"] == best_price)

    return jsonify({
        "query": query,
        "prices": items
    })

# ====================
# RUN
# ====================
if __name__ == "__main__":
    print("OpenWeb Ninja API key set:", bool(OPENWEBNINJA_API_KEY))
    app.run(debug=True)

