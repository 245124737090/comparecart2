import random
import re
import time
import requests
import os
from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
from bs4 import BeautifulSoup
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# REQUIRED for login/session
app.secret_key = "super-secret-key"

# Temporary in-memory user storage
users = {}

SCRAPERAPI_API_KEY = os.getenv('SCRAPERAPI_API_KEY')
if not SCRAPERAPI_API_KEY:
    print("WARNING: SCRAPERAPI_API_KEY not set - using fallback prices only")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_amazon_price(query):
    if SCRAPERAPI_API_KEY:
        try:
            params = {
                'api_key': SCRAPERAPI_API_KEY,
                'query': query,
                'country': 'IN',
                'tld': 'amazon.in'
            }
            r = requests.get(
                "https://api.scraperapi.com/structured/amazon/search",
                params=params,
                timeout=20
            )

            if r.status_code == 200:
                data = r.json()
                if data.get('results'):
                    product = data['results'][0]
                    price = product.get('price')
                    if price:
                        price = int(re.search(r'[\d,]+', str(price)).group().replace(',', ''))
                        return {
                            "retailer": "Amazon",
                            "price": price,
                            "status": product.get('availability', 'In Stock'),
                            "shipping": "Free",
                            "url": product.get('link'),
                            "estimated": False,
                            "source": "ScraperAPI"
                        }
        except Exception as e:
            print("[DEBUG] ScraperAPI error:", e)

    try:
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        price_elem = soup.select_one(".a-price-whole")
        if price_elem:
            price = int(price_elem.text.replace(',', '').strip())
            return {
                "retailer": "Amazon",
                "price": price,
                "status": "In Stock",
                "shipping": "Free",
                "url": url,
                "estimated": False,
                "source": "Direct"
            }
    except Exception as e:
        print("[DEBUG] Direct scrape error:", e)

    return None

def get_flipkart_price(base_price, query):
    variation = random.uniform(-0.03, 0.03)
    price = int(base_price * (1 + variation))
    return {
        "retailer": "Flipkart",
        "price": price,
        "status": "In Stock",
        "shipping": "Free",
        "url": f"https://www.flipkart.com/search?q={query.replace(' ', '+')}",
        "estimated": True
    }

@app.route("/api/prices")
def api_prices():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"prices": [], "error": "No query provided"})

    amazon = get_amazon_price(query)
    prices = []

    if amazon:
        base_price = amazon["price"]
        prices.append(amazon)
    else:
        base_price = 66748
        prices.append({
            "retailer": "Amazon (Estimate)",
            "price": base_price,
            "status": "In Stock",
            "shipping": "Free",
            "url": f"https://www.amazon.in/s?k={query.replace(' ', '+')}",
            "estimated": True
        })

    prices.append(get_flipkart_price(base_price, query))
    prices.sort(key=lambda x: x["price"])
    prices[0]["best"] = True

    return jsonify({"prices": prices})

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
        return redirect(url_for("home"))

    if email in users:
        flash("User already exists. Please log in.")
        return redirect(url_for("home"))

    users[email] = {
        "password_hash": generate_password_hash(password)
    }
    session["user_email"] = email
    flash("Account created successfully.")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    user = users.get(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return redirect(url_for("home"))

    session["user_email"] = email
    flash("Logged in successfully.")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    flash("Logged out.")
    return redirect(url_for("home"))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)




