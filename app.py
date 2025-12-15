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
@app.route("/api/prices")
def api_prices():
    query = request.args.get("query", "").strip()
    if not query:
        return {"error": "query required"}, 400

    base_price = 50000
    prices = [
        {
            "store": "Flipkart",
            "price": base_price,
            "shipping": "Free",
            "status": "In Stock",
            "url": f"https://www.flipkart.com/search?q={query}"
        },
        {
            "store": "Amazon",
            "price": base_price + 2000,
            "shipping": "Free",
            "status": "In Stock",
            "url": f"https://www.amazon.in/s?k={query}"
        }
    ]
    min_price = min(p["price"] for p in prices)
    for p in prices:
        p["best"] = (p["price"] == min_price)
    return {"query": query, "prices": prices}

if __name__ == "__main__":
    app.run(debug=True)
