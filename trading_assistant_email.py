import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load secrets from .streamlit/secrets.toml
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Streamlit config
st.set_page_config(page_title="Trading Assistant", layout="wide")
st.title("📈 Trading 212 Assistant + Email Alerts")

# User inputs
ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=1)
period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map[interval]

# Fetch and cache data
@st.cache_data(ttl=300)
def get_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# Apply indicators and strategy
def apply_strategy(df):
    close = df['Close']
    volume = df['Volume']

    df['sma10'] = ta.trend.sma_indicator(close=close, window=10)
    df['sma30'] = ta.trend.sma_indicator(close=close, window=30)
    df['rsi'] = ta.momentum.rsi(close=close, window=14)

    macd = ta.trend.macd(close)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['volume_ma'] = ta.trend.sma_indicator(volume, window=20)

    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1

    return df

# Email function
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

# Main logic
if ticker:
    try:
        df = get_data(ticker, period, interval)
        if df.empty:
            st.warning("⚠️ No data returned. Check the ticker or interval.")
            st.stop()

        df = apply_strategy(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        if prev['signal'] != latest['signal'] and latest['signal'] != st.session_state.last_signal:
            st.session_state.last_signal = latest['signal']

            # Build message body
            message = (
                f"Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal Line: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
            )

            if latest['signal'] == 1:
                signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
                send_email(f"BUY Alert for {ticker}", message)
            elif latest['signal'] == -1:
                signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"
                send_email(f"SELL Alert for {ticker}", message)

        # Display signal
        st.subheader(f"Signal: {signal_text}")
        col1, col2, col3 = st.columns(3)
        col1.metric("RSI (14)", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")

        # Plotting
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        # Price chart with SMA
        ax1.plot(df.index, df['Close'], label='Close Price', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
        ax1.bar(df.index, df['Volume'], color='lightgray', alpha=0.3, label='Volume')
        ax1.set_title(f"{ticker} — Price & SMAs")
        ax1.legend()

        # RSI
        ax2.plot(df.index, df['rsi'], label='RSI (14)', color='purple')
        ax2.axhline(70, linestyle='--', color='red')
        ax2.axhline(30, linestyle='--', color='green')
        ax2.set_title("RSI Indicator")
        ax2.legend()

        # MACD
        ax3.plot(df.index, df['macd'], label='MACD', color='blue')
        ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, linestyle='--', color='black')
        ax3.set_title("MACD")
        ax3.legend()

        plt.tight_layout()
        st.pyplot(fig)

        # Data display
        with st.expander("📋 View Raw Data"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"An error occurred: {e}")
