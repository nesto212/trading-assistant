import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from difflib import get_close_matches
import matplotlib.pyplot as plt

# --- Email Config ---
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- Streamlit App Setup ---
st.set_page_config(page_title="Trading Assistant", layout="wide")
st.title("📈 Trading Assistant with Alerts")

# --- Ticker Input ---
ticker_input = st.text_input("Enter ticker(s), separated by commas (e.g. AAPL, TSLA, AMZN):", "TSLA")
interval = st.selectbox("Select Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)
period_map = {
    "1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d",
    "1d": "3mo", "1wk": "6mo", "1mo": "1y"
}
period = period_map[interval]

# --- Cached Data Fetch ---
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    df.dropna(inplace=True)
    return df

# --- Email Alert ---
def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        st.info("📤 Email alert sent.")
    except Exception as e:
        st.error(f"❌ Email error: {e}")

# --- Strategy ---
def apply_strategy(df):
    if not {'Close', 'Volume'}.issubset(df.columns):
        st.warning("Missing 'Close' or 'Volume' columns.")
        df['signal'] = 0
        return df

    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['signal'] = 0
    df.loc[df['sma10'] > df]()
