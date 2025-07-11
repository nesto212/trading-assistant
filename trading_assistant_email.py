import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load secrets
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading 212 Assistant + Email Alerts")

ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=1)
period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map[interval]

@st.cache_data(ttl=300)
def get_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

def apply_strategy(df):
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1
    return df

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
        st.error(f"❌ Failed to send email: {e}")

if ticker:
    df = get_data(ticker, period, interval)
    df = apply_strategy(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signal_text = "⚠️ HOLD — No new signal"
    if prev['signal'] != latest['signal']:
        if latest['signal'] == 1:
            signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
            send_email(f"BUY Alert for {ticker}", f"{signal_text}\nSMA(10) crossed above SMA(30).")
        elif latest['signal'] == -1:
            signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"
            send_email(f"SELL Alert for {ticker}", f"{signal_text}\nSMA(10) crossed below SMA(30).")
    st.subheader(f"Signal: {signal_text}")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df['Close'], label='Price', color='gray')
    ax.plot(df['sma10'], label='SMA 10', color='blue')
    ax.plot(df['sma30'], label='SMA 30', color='red')
    ax.legend()
    st.pyplot(fig)
    with st.expander("📋 View Data"):
        st.dataframe(df.tail(15))
