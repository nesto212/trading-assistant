import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load secrets (make sure .streamlit/secrets.toml has email creds)
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading Assistant + Email Alerts")

# UI Inputs
ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox(
    "Interval",
    ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
    index=8,
)

# Map intervals to periods (long enough to get data)
period_map = {
    "1m": "7d",
    "2m": "60d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "60d",
    "90m": "60d",
    "1h": "730d",
    "1d": "730d",
    "5d": "730d",
    "1wk": "730d",
    "1mo": "1460d",
    "3mo": "1460d",
}
period = period_map.get(interval, "60d")

# Cache data fetch (must be outside other functions/classes)
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

def apply_strategy(df):
    # Ensure needed columns exist
    if not {'Close', 'Volume'}.issubset(df.columns):
        st.warning("Data missing required columns 'Close' and/or 'Volume'. Adding default 'signal' = 0")
        df['signal'] = 0
        return df

    close = df['Close']
    volume = df['Volume']

    # Apply indicators - flatten series to 1D with .values if needed
    df['sma10'] = ta.trend.sma_indicator(close=close, window=10).values
    df['sma30'] = ta.trend.sma_indicator(close=close, window=30).values
    df['rsi'] = ta.momentum.rsi(close=close, window=14).values

    macd_indicator = ta.trend.MACD(close=close)
    df['macd'] = macd_indicator.macd().values
    df['macd_signal'] = macd_indicator.macd_signal().values

    df['volume_ma'] = ta.trend.sma_indicator(close=volume, window=20).values

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
    try:
        df = fetch_data(ticker, period, interval)

        if df.empty:
            st.warning("⚠️ No data returned. Check ticker symbol, interval, or wait for markets to open.")
            st.stop()

        df = apply_strategy(df)

        # Check if signal column is present
        if 'signal' not in df.columns or len(df) < 2:
            st.warning("Not enough data or 'signal' column missing to generate alerts.")
            st.stop()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        if (prev['signal'] != latest['signal']) and (latest['signal'] != st.session_state.last_signal):
            st.session_state.last_signal = latest['signal']

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

        st.subheader(f"Signal: {signal_text}")

        col1, col2, col3 = st.columns(3)
        col1.metric("RSI (14)", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        ax1.plot(df.index, df['Close'], label='Close Price', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
        ax1.bar(df.index, df['Volume'], color='lightgray', alpha=0.3, label='Volume')
        ax1.set_title(f"{ticker} — Price & SMAs")
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

        with st.expander("📋 View Raw Data"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"An error occurred: {e}")
