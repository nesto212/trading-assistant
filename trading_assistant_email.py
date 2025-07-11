import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# --- Email Config from secrets.toml ---
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- Streamlit Setup ---
st.set_page_config(page_title="Trading Assistant + Alerts", layout="wide")
st.title("📈 Trading Assistant with Email Alerts")

# --- User Inputs ---
ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)
period_map = {"1d": "3mo", "1wk": "6mo", "1mo": "1y"}
period = period_map[interval]

# --- Data Fetch Function ---
@st.cache_data(ttl=600)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# --- Strategy Logic ---
def apply_strategy(df):
    if not {'Close', 'Volume'}.issubset(df.columns):
        st.warning("⚠️ Data missing required 'Close' or 'Volume'. Adding default 'signal' = 0.")
        df["signal"] = 0
        return df

    close = df['Close']
    volume = df['Volume']

    df['sma10'] = ta.trend.sma_indicator(close=close, window=10)
    df['sma30'] = ta.trend.sma_indicator(close=close, window=30)
    df['rsi'] = ta.momentum.rsi(close=close, window=14)

    macd = ta.trend.MACD(close)
    df['macd'] = macd.macd().squeeze()
    df['macd_signal'] = macd.macd_signal().squeeze()

    df['volume_ma'] = ta.trend.sma_indicator(close=volume, window=20)

    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1

    return df

# --- Email Function ---
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
        st.success("📤 Email sent successfully.")
    except Exception as e:
        st.error(f"❌ Email failed: {e}")

# --- Main Logic ---
if ticker:
    try:
        df = fetch_data(ticker, period, interval)

        if df.empty or len(df) < 2:
            st.warning("⚠️ Not enough data.")
            st.stop()

        df = apply_strategy(df)

        if 'signal' not in df.columns:
            st.warning("⚠️ 'signal' column not found. Skipping signal check.")
            df['signal'] = 0

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        if latest['signal'] != prev['signal'] and latest['signal'] != st.session_state.last_signal:
            st.session_state.last_signal = latest['signal']

            msg_body = (
                f"Ticker: {ticker}\n"
                f"Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Close Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f} | Signal: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f} | SMA30: {latest['sma30']:.2f}"
            )

            if latest['signal'] == 1:
                signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
                send_email(f"BUY Alert for {ticker}", msg_body)
            elif latest['signal'] == -1:
                signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"
                send_email(f"SELL Alert for {ticker}", msg_body)

        st.subheader(f"Signal: {signal_text}")

        col1, col2, col3 = st.columns(3)
        col1.metric("RSI", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")

        # --- Plotting ---
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        ax1.plot(df.index, df['Close'], label='Close Price', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
        ax1.set_title("Price & SMAs")
        ax1.legend()

        ax2.plot(df.index, df['rsi'], label='RSI (14)', color='purple')
        ax2.axhline(70, linestyle='--', color='red')
        ax2.axhline(30, linestyle='--', color='green')
        ax2.set_title("RSI Indicator")
        ax2.legend()

        ax3.plot(df.index, df['macd'], label='MACD', color='blue')
        ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, linestyle='--', color='black')
        ax3.set_title("MACD")
        ax3.legend()

        plt.tight_layout()
        st.pyplot(fig)

        with st.expander("📊 View Raw Data"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"An error occurred: {e}")
