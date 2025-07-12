import streamlit as st
import yfinance as yf
import pandas as pd
from ta.trend import MACD
from ta.momentum import RSIIndicator
import requests
from difflib import get_close_matches
import smtplib
from email.message import EmailMessage

st.set_page_config(page_title="Trading Assistant", layout="wide")

VALID_TICKERS_URL = "https://query1.finance.yahoo.com/v1/finance/search?q="

@st.cache_data(ttl=600)
def fetch_data(ticker, period="7d", interval="1h"):
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError(f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

def suggest_tickers(query):
    if not query or len(query) < 1:
        return []
    try:
        r = requests.get(VALID_TICKERS_URL + query)
        items = r.json().get("quotes", [])
        return [item["symbol"] for item in items if "symbol" in item]
    except Exception:
        return []

def calculate_signals(df):
    macd = MACD(df["Close"]).macd_diff()
    rsi = RSIIndicator(df["Close"]).rsi()
    df["Signal"] = "Hold"
    df.loc[(macd > 0) & (rsi < 30), "Signal"] = "Buy"
    df.loc[(macd < 0) & (rsi > 70), "Signal"] = "Sell"
    return df

def send_email_alert(to_email, subject, body):
    # Use your own email configuration here
    EMAIL_ADDRESS = "your_email@example.com"
    EMAIL_PASSWORD = "your_password"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

st.title("📈 Trading Assistant with Real-Time Lookup and Alerts")

user_input = st.text_input("Enter tickers (comma-separated):", value="AAPL, MSFT, GOOGL")
interval = st.selectbox("Select interval", options=["1m", "5m", "15m", "1h", "1d"], index=3)

# Auto-lookup suggestions
search_input = st.text_input("🔍 Lookup a ticker:")
if search_input:
    suggestions = suggest_tickers(search_input)
    if suggestions:
        st.info(f"Suggestions: {', '.join(suggestions[:5])}")
    else:
        st.warning("No suggestions found.")

tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()]
period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map.get(interval, "7d")

email_alerts = st.checkbox("📧 Send email alerts")
recipient_email = st.text_input("Enter your email (for alerts):") if email_alerts else None

for ticker in tickers:
    try:
        df = fetch_data(ticker, period, interval)
        df = calculate_signals(df)
        last_signal = df["Signal"].iloc[-1]

        st.subheader(f"{ticker} — Last Signal: {last_signal}")
        st.line_chart(df["Close"])
        st.dataframe(df.tail(10), use_container_width=True)

        if email_alerts and last_signal in ["Buy", "Sell"]:
            subject = f"{ticker} Trading Signal: {last_signal}"
            body = f"The latest signal for {ticker} is {last_signal}.\n\nLast Price: {df['Close'].iloc[-1]}"
            send_email_alert(recipient_email, subject, body)
            st.success(f"Alert sent for {ticker} to {recipient_email}")

    except ValueError as e:
        close_matches = suggest_tickers(ticker)
        if close_matches:
            st.warning(f"{e}. Did you mean: {', '.join(close_matches[:3])}?")
        else:
            st.error(str(e))
    except Exception as e:
        st.error(f"Unexpected error with {ticker}: {e}")
