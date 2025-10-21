# MJR_Dashboard

A minimal, professional **finance dashboard** built with Streamlit and Yahoo Finance.

## Features
- Enter or select tickers; choose date range
- Price chart, normalized cumulative returns
- Daily return correlations (table + heatmap)
- Fundamentals snapshot + financial statements (where available)
- Optional CSV downloads (prices, daily returns, cumulative returns)

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
1. Push `app.py` and `requirements.txt` to a **public GitHub repository**.
2. Go to **share.streamlit.io** (Streamlit Community Cloud) → **New app**.
3. Select your repo/branch, set **Main file path** to `app.py`, then **Deploy**.
4. In the app, enter tickers (e.g., `AAPL, MSFT, GOOG`) and adjust the date range.
