require("dotenv").config();
const express = require("express");
const axios = require("axios");
const app = express();

const PORT = process.env.PORT || 5000;
const RAINFOREST_API_KEY = process.env.RAINFOREST_API_KEY;

// Helper: INR currency
function parsePriceToNumber(value){
  if(!value) return null;
  if(typeof value === "number") return value;
  return Number(
    String(value)
      .replace(/[^\d.]/g,"")
  ) || null;
}

// --- Amazon via Rainforest API (3rd party) ---
async function getAmazonPrice(query){
  try{
    const url = "https://api.rainforestapi.com/request";
    const params = {
      api_key: RAINFOREST_API_KEY,
      type: "search",
      amazon_domain: "amazon.in",
      search_term: query,
      sort_by: "featured"
    };

    const { data } = await axios.get(url, { params });

    const first = data.search_results && data.search_results[0];
    if(!first) return null;

    const priceObj = first.price || {};
    const price = parsePriceToNumber(priceObj.raw || priceObj.value);

    return {
      store: "Amazon",
      price,
      url: first.link || "https://www.amazon.in",
      status: first.availability ? first.availability.type || "In Stock" : "In Stock",
      shipping: "See on Amazon",
    };
  }catch(err){
    console.error("Amazon error:", err.message);
    return null;
  }
}

// --- Flipkart via public scraper API (3rd party) ---
async function getFlipkartPrice(query){
  try{
    // public scraper: https://dvishal485.github.io/flipkart-scraper-api/ [web:16]
    const url = `https://flipkart-scraper-api.vercel.app/search/${encodeURIComponent(query)}`;

    const { data } = await axios.get(url);
    const results = data.result || data.results || [];

    const first = results[0];
    if(!first) return null;

    const price = parsePriceToNumber(first.current_price || first.price);

    return {
      store: "Flipkart",
      price,
      url: first.link || first.query_url || "https://www.flipkart.com",
      status: first.in_stock === false ? "Out of Stock" : "In Stock",
      shipping: "See on Flipkart",
    };
  }catch(err){
    console.error("Flipkart error:", err.message);
    return null;
  }
}

// --- Main prices endpoint used by your frontend ---
app.get("/api/prices", async (req, res) => {
  const query = (req.query.query || "").trim();
  if(!query){
    return res.json({ prices: [] });
  }

  try{
    // Query both in parallel
    const [amazon, flipkart] = await Promise.all([
      getAmazonPrice(query),
      getFlipkartPrice(query)
    ]);

    // Filter out nulls
    const items = [amazon, flipkart].filter(Boolean);

    if(items.length === 0){
      return res.json({ prices: [] });
    }

    // Mark best (cheapest) item
    const sorted = [...items].filter(p => p.price != null).sort((a,b) => a.price - b.price);
    if(sorted.length){
      const bestPrice = sorted[0].price;
      items.forEach(p => {
        p.best = (p.price != null && p.price === bestPrice);
      });
    }else{
      items.forEach(p => p.best = false);
    }

    res.json({ prices: items });
  }catch(e){
    console.error("API /api/prices error:", e.message);
    res.status(500).json({ prices: [] });
  }
});

// static hosting for your HTML app (adjust path)
app.use(express.static("public"));

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
