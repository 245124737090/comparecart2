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
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def _parse_price(text):
    """Convert price string like '₹99,999' to integer."""
    if not text:
        return None
    digits = "".join(c for c in str(text) if c.isdigit())
    return int(digits) if digits else None

def _searchapi_prices(query):
    """Get Amazon + Flipkart prices using SerpApi."""
    if not SERPAPI_KEY:
        return []

    items = []

    for store in ["amazon", "flipkart"]:
        try:
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "engine": f"{store}_search",
                    "q": query,
                    "location": "India",
                    "hl": "en",
                    "gl": "in",
                    "api_key": SERPAPI_KEY,
                },
                timeout=10,
            )
            data = resp.json()
            # SerpApi returns different structures per engine
            results = data.get("shopping_results") or data.get("organic_results") or []

            if not results:
                continue

            first = results[0]
            price = _parse_price(first.get("price") or first.get("raw_price"))

            if not price:
                continue

            items.append({
                "store": store.capitalize(),
                "price": price,
                "shipping": "See on site",
                "status": "In Stock",
                "url": first.get("link") or first.get("product_link"),
            })
        except Exception as e:
            print(f"{store.capitalize()} SerpApi error:", e)

    return items

# --------------------
# API ENDPOINT
# --------------------
@app.route("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query required", "prices": []}), 400

    items = _searchapi_prices(query)

    if not items:
        return jsonify({"query": query, "prices": []})

    # mark best (cheapest) price
    valid = [p for p in items if p.get("price") is not None]
    if valid:
        best_price = min(p["price"] for p in valid)
        for p in items:
            p["best"] = p["price"] == best_price
    else:
        for p in items:
            p["best"] = False

    return jsonify({"query": query, "prices": items})

# --------------------
if __name__ == "__main__":
    app.run(debug=True)

