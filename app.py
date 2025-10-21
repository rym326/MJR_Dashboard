import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import altair as alt
from datetime import date, timedelta

# -------------------------
# Page config & styling
# -------------------------
st.set_page_config(
    page_title="Finance Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✅ FIXED CSS BLOCK
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
            margin: auto;
        }
        .metric-card {
            border: 1px solid #eaeaea;
            border-radius: 16px;
            padding: 16px;
            background: white;
        }
    </style>
""", unsafe_allow_html=True)


# -------------------------
# Helpers
# -------------------------
@st.cache_data(show_spinner=False)
def fetch_prices(tickers, start, end):
    try:
        data = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)
        # Handle single ticker vs multi-index columns
        if isinstance(tickers, str) or len(tickers) == 1:
            df = data[['Close']].copy()
            df.columns = pd.MultiIndex.from_product([['Close'], [tickers if isinstance(tickers, str) else tickers[0]]])
            return df
        return data[['Close']]
    except Exception as e:
        st.warning(f"Price download failed: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def fetch_fundamentals(ticker):
    t = yf.Ticker(ticker)
    out = {}
    # Each may fail depending on ticker & API changes
    for attr in ["info", "fast_info", "financials", "balance_sheet", "cashflow", "earnings", "quarterly_earnings", "income_stmt", "quarterly_income_stmt"]:
        try:
            out[attr] = getattr(t, attr)
        except Exception:
            out[attr] = None
    return out

def to_long_close(close_wide: pd.DataFrame) -> pd.DataFrame:
    """Convert Close wide (MultiIndex) to long tidy format."""
    if close_wide.empty:
        return close_wide
    if isinstance(close_wide.columns, pd.MultiIndex):
        long_df = close_wide.copy()
        long_df.columns = [c[1] for c in long_df.columns]  # keep just ticker level
    else:
        long_df = close_wide.copy()
    long_df = long_df.rename_axis("Date").reset_index().melt("Date", var_name="Ticker", value_name="Close")
    long_df = long_df.dropna(subset=["Close"])
    return long_df

def normalized_returns(close_wide: pd.DataFrame) -> pd.DataFrame:
    if close_wide.empty:
        return close_wide
    cl = close_wide.copy()
    if isinstance(cl.columns, pd.MultiIndex):
        cl.columns = [c[1] for c in cl.columns]
    cl = cl.ffill().bfill()
    norm = cl / cl.iloc[0] - 1.0
    return norm

def daily_returns(close_wide: pd.DataFrame) -> pd.DataFrame:
    if close_wide.empty:
        return close_wide
    cl = close_wide.copy()
    if isinstance(cl.columns, pd.MultiIndex):
        cl.columns = [c[1] for c in cl.columns]
    ret = cl.pct_change().dropna(how="all")
    return ret

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("⚙️ Controls")

default_tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "DELL"]
hardcoded = st.sidebar.multiselect("Default tickers (built-in)", options=default_tickers, default=["AAPL","MSFT","GOOG"])

user_ticker_input = st.sidebar.text_input("Add tickers (comma-separated)", value="")
user_tickers = [t.strip().upper() for t in user_ticker_input.split(",") if t.strip()]

tickers = sorted(set(hardcoded + user_tickers))
if not tickers:
    st.warning("Select or type at least one ticker to begin.")
    st.stop()

today = date.today()
default_start = today - timedelta(days=365*5)
start_date = st.sidebar.date_input("Start date", value=default_start, max_value=today - timedelta(days=1))
end_date = st.sidebar.date_input("End date", value=today, max_value=today)

benchmark = st.sidebar.text_input("Benchmark (optional, e.g., ^GSPC for S&P 500)", value="^GSPC").strip()

st.sidebar.markdown("---")
download_toggle = st.sidebar.checkbox("Enable data downloads", value=True)

# -------------------------
# Header
# -------------------------
st.title("📈 Finance Dashboard")
st.caption("Interactive price charts, cumulative returns, correlations, and fundamentals powered by Yahoo Finance.")

st.write(f"**Tickers:** {', '.join(tickers)}  \n**Date range:** {start_date} → {end_date}")

# -------------------------
# Data
# -------------------------
prices = fetch_prices(tickers, start_date, end_date)
if benchmark:
    bench_prices = fetch_prices([benchmark], start_date, end_date)

close_wide = prices.xs("Close", axis=1, level=0) if isinstance(prices.columns, pd.MultiIndex) else prices
long_close = to_long_close(prices)

# -------------------------
# Metrics row
# -------------------------
if not close_wide.empty:
    ret_daily = daily_returns(close_wide)
    cum = normalized_returns(close_wide)

    latest = close_wide.ffill().iloc[-1]
    ytd_mask = close_wide.index >= pd.to_datetime(f"{today.year}-01-01")
    ytd = (close_wide[ytd_mask].ffill().iloc[-1] / close_wide[ytd_mask].ffill().iloc[0] - 1.0) if ytd_mask.any() else pd.Series(index=close_wide.columns)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Latest Prices")
        st.dataframe(latest.round(2).rename("Price ($)").to_frame(), use_container_width=True)
    with c2:
        st.subheader("YTD Return")
        st.dataframe((ytd*100).round(2).rename("YTD %").to_frame(), use_container_width=True)
    with c3:
        st.subheader("Volatility (30d)")
        vol30 = ret_daily.rolling(30).std().iloc[-1] * np.sqrt(252) * 100
        st.dataframe(vol30.round(2).rename("Ann. Vol %").to_frame(), use_container_width=True)

# -------------------------
# Tabs
# -------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Price & Returns", "📉 Correlations", "📚 Fundamentals", "⬇️ Downloads"])

# ---- Tab 1: Price & Returns
with tab1:
    left, right = st.columns([2,1])
    with left:
        st.subheader("Adjusted Close Price")
        if not long_close.empty:
            price_chart = alt.Chart(long_close).mark_line().encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Close:Q", title="Price ($)", scale=alt.Scale(zero=False)),
                color=alt.Color("Ticker:N", legend=alt.Legend(title="Ticker"))
            ).properties(height=380)
            st.altair_chart(price_chart, use_container_width=True)
        else:
            st.info("No price data yet.")
    with right:
        st.subheader("Normalized Cumulative Return")
        if not close_wide.empty:
            cum = normalized_returns(close_wide)
            cum_long = cum.rename_axis("Date").reset_index().melt("Date", var_name="Ticker", value_name="Cumulative Return")
            cum_chart = alt.Chart(cum_long).mark_line().encode(
                x="Date:T",
                y=alt.Y("Cumulative Return:Q", axis=alt.Axis(format="%"), title="Cumulative Return"),
                color="Ticker:N"
            ).properties(height=380)
            st.altair_chart(cum_chart, use_container_width=True)
        else:
            st.info("No return data yet.")

    if benchmark:
        st.markdown("**Benchmark Comparison**")
        try:
            bench_close = bench_prices.xs("Close", axis=1, level=0)
            merged = close_wide.join(bench_close.rename(columns={bench_close.columns[0]: "Benchmark"}), how="inner")
            norm = merged / merged.iloc[0] - 1
            long_bench = norm.rename_axis("Date").reset_index().melt("Date", var_name="Ticker", value_name="Cumulative Return")
            chart_bench = alt.Chart(long_bench).mark_line().encode(
                x="Date:T",
                y=alt.Y("Cumulative Return:Q", axis=alt.Axis(format="%")),
                color="Ticker:N"
            ).properties(height=280)
            st.altair_chart(chart_bench, use_container_width=True)
        except Exception as e:
            st.warning(f"Benchmark plotting issue: {e}")

# ---- Tab 2: Correlations
with tab2:
    st.subheader("Return Correlations (Daily)")
    if not close_wide.empty:
        r = daily_returns(close_wide).corr()
        st.dataframe(r.round(3), use_container_width=True)
        # Heatmap with Altair
        heat_df = r.reset_index().melt("index")
        heat_df.columns = ["X","Y","Correlation"]
        heat = alt.Chart(heat_df).mark_rect().encode(
            x=alt.X("X:N", sort=list(r.columns)),
            y=alt.Y("Y:N", sort=list(r.columns)),
            tooltip=["X","Y",alt.Tooltip("Correlation:Q", format=".2f")],
            color=alt.Color("Correlation:Q", scale=alt.Scale(scheme="blues"))
        ).properties(height=420)
        st.altair_chart(heat, use_container_width=True)
    else:
        st.info("Add tickers to see correlations.")

# ---- Tab 3: Fundamentals
with tab3:
    st.subheader("Company Fundamentals")
    selected = st.selectbox("Select ticker", options=tickers)
    fundamentals = fetch_fundamentals(selected)

    cols = st.columns(3)
    info = fundamentals.get("info") or {}
    fast = fundamentals.get("fast_info") or {}
    with cols[0]:
        st.markdown("**Snapshot**")
        key_rows = {
            "longName": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "marketCap": info.get("marketCap"),
            "beta": info.get("beta"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "dividendYield": info.get("dividendYield"),
        }
        st.dataframe(pd.Series(key_rows, name=selected))
    with cols[1]:
        st.markdown("**Income Statement / Earnings**")
        try:
            inc = fundamentals.get("financials")
            if isinstance(inc, pd.DataFrame) and not inc.empty:
                st.caption("Annual Financials")
                st.dataframe(inc.head(20))
        except Exception:
            pass
        try:
            q_earn = fundamentals.get("quarterly_earnings")
            if isinstance(q_earn, pd.DataFrame) and not q_earn.empty:
                st.caption("Quarterly Earnings")
                st.dataframe(q_earn.tail(12))
        except Exception:
            pass
    with cols[2]:
        st.markdown("**Balance Sheet / Cash Flow**")
        for key in ["balance_sheet", "cashflow"]:
            df = fundamentals.get(key)
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.caption(key.replace("_"," ").title())
                st.dataframe(df.head(20))

# ---- Tab 4: Downloads
with tab4:
    st.subheader("Export Data")
    if download_toggle and not close_wide.empty:
        ret = daily_returns(close_wide)
        cum = normalized_returns(close_wide)

        def to_csv_bytes(df):
            return df.to_csv(index=True).encode("utf-8")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("Download Prices (CSV)", to_csv_bytes(close_wide), file_name="prices.csv")
        with c2:
            st.download_button("Download Daily Returns (CSV)", to_csv_bytes(ret), file_name="daily_returns.csv")
        with c3:
            st.download_button("Download Cumulative Returns (CSV)", to_csv_bytes(cum), file_name="cumulative_returns.csv")
    else:
        st.info("Enable downloads in the sidebar to export data.")
