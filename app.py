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
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else None

def _serpapi_prices(query):
    """Fetch Amazon, Flipkart, Croma, Reliance via Google Shopping"""
    if not SERPAPI_KEY:
        return []

    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_shopping",
                "q": query,
                "location": "India",
                "hl": "en",
                "gl": "in",
                "api_key": SERPAPI_KEY,
            },
            timeout=10,
        )

        data = resp.json()
        results = data.get("shopping_results", [])
        items = []

        for r in results:
            source = (r.get("source") or "").lower()

            # Only keep the 4 stores
            if "amazon" in source:
                store = "Amazon"
            elif "flipkart" in source:
                store = "Flipkart"
            elif "croma" in source:
                store = "Croma"
            elif "reliance" in source:
                store = "Reliance Digital"
            else:
                continue

            items.append({
                "store": store,
                "price": _parse_price(r.get("price")),
                "shipping": "See on site",
                "status": "In Stock",
                "url": r.get("link"),
            })

        return items

    except Exception as e:
        print("SerpApi error:", e)
        return []

# --------------------
# API ENDPOINT
# --------------------
@app.route("/api/prices")
def api_prices():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query required", "prices": []}), 400

    items = _serpapi_prices(query)

    if not items:
        return jsonify({"query": query, "prices": []})

    # Mark best (lowest) price
    valid = [p for p in items if p["price"] is not None]
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


