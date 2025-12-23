from flask import Flask, request, jsonify
from flask_cors import CORS
from scraper.amazon import amazon_price
from scraper.flipkart import flipkart_price

app = Flask(__name__)
CORS(app)

@app.route("/api/prices")
def prices():
    query = request.args.get("query")

    amazon = amazon_price(query)
    flipkart = flipkart_price(query)

    prices = [amazon, flipkart]
    prices.sort(key=lambda x: x["price"])

    prices[0]["best"] = True

    return jsonify({"prices": prices})

if __name__ == "__main__":
    app.run(debug=True)
