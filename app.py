from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# simple in-memory "database"
users = {}  # {"email": {"password_hash": "..."}}

@app.route("/")
def home():
    user_email = session.get("user_email")
    return render_template("index.html", user_email=user_email)

@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Email and password are required.")
        return redirect(url_for("home") + "#signup")

    if email in users:
        flash("User already exists. Please log in.")
        return redirect(url_for("home") + "#login")

    users[email] = {
        "password_hash": generate_password_hash(password)
    }
    session["user_email"] = email
    flash("Account created and logged in.")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    user = users.get(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return redirect(url_for("home") + "#login")

    session["user_email"] = email
    flash("Logged in successfully.")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    flash("Logged out.")
    return redirect(url_for("home"))

# existing demo prices api
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


if __name__ == "__main__":
    app.run(debug=True)

