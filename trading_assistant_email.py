import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Trading Assistant", layout="wide")
st.title("📈 Trading Assistant with Signals & Email Alerts")

# --- Email Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com"  # <-- Replace with your email
EMAIL_PASSWORD = "your_app_password"    # <-- Replace with your app-specific password

# --- Data Fetching ---
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(1)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

# --- Technical Indicators ---
def compute_indicators(df):
    df["EMA20"] = ta.trend.EMAIndicator(df["Close"], window=20).ema_indicator()
    df["RSI"] = ta.momentum.RSIIndicator(df["Close"]).rsi()
    return df.dropna()

# --- Signal Logic ---
def generate_signal(df):
    latest = df.iloc[-1]
    if latest["RSI"] < 30 and latest["Close"] > latest["EMA20"]:
        return "BUY"
    elif latest["RSI"] > 70 and latest["Close"] < latest["EMA20"]:
        return "SELL"
    else:
        return "HOLD"

# --- Email Sender ---
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_ADDRESS
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Email failed: {e}")
        return False

# --- Sidebar Inputs ---
tickers = st.text_input("📥 Enter tickers (comma-separated)", value="AAPL,MSFT,GOOGL").upper().split(",")
interval = st.selectbox("⏱️ Interval", ["5m", "15m", "1h", "1d"])
period_map = {"5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map[interval]

send_email_alerts = st.checkbox("📧 Send Email Alerts for BUY/SELL signals")

# --- Scan Tickers ---
alerts = []

for ticker in tickers:
    ticker = ticker.strip()
    st.subheader(f"📊 {ticker}")
    try:
        df = fetch_data(ticker, period, interval)
        df = compute_indicators(df)
        signal = generate_signal(df)
        latest = df.iloc[-1]

        # --- Metrics ---
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Price", f"${latest['Close']:.2f}")
            st.metric("RSI", f"{latest['RSI']:.2f}")
            st.metric("Signal", signal)

        # --- Chart ---
        with col2:
            st.line_chart(df[["Close", "EMA20"]])

        # --- Email Alert ---
        if send_email_alerts and signal in ["BUY", "SELL"]:
            alerts.append(f"{ticker}: {signal} at ${latest['Close']:.2f}")

    except Exception as e:
        st.error(f"Error with {ticker}: {e}")

# --- Send Alert Email ---
if alerts:
    body = "\n".join(alerts)
    subject = "📈 Trading Signal Alert"
    if send_email_alerts:
        if send_email(subject, body):
            st.success("✅ Email alert sent!")
        else:
            st.warning("⚠️ Email not sent.")
