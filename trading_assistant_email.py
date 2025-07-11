import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load email credentials securely from secrets
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Streamlit UI setup
st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading 212 Assistant + Email Alerts")

# Ticker and interval input
ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=1)
period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map[interval]

# Cache the data fetch
@st.cache_data(ttl=300)
def get_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# Apply trading strategy with indicators
def apply_strategy(df):
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.macd(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['volume_ma'] = ta.trend.sma_indicator(df['Volume'], window=20)

    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1
    return df

# Email alert function
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
            st.warning("No data returned. Please check the ticker or interval.")
            st.stop()

        df = apply_strategy(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Signal handling
        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        if prev['signal'] != latest['signal'] and latest['signal'] != st.session_state.last_signal:
            st.session_state.last_signal = latest['signal']
            if latest['signal'] == 1:
                signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
                message = (
                    f"{signal_text}\n"
                    f"SMA(10) crossed above SMA(30).\n"
                    f"RSI: {latest['rsi']:.2f}\n"
                    f"MACD: {latest['macd']:.2f}, Signal: {latest['macd_signal']:.2f}"
                )
                send_email(f"BUY Alert for {ticker}", message)
            elif latest['signal'] == -1:
                signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"
                message = (
                    f"{signal_text}\n"
                    f"SMA(10) crossed below SMA(30).\n"
                    f"RSI: {latest['rsi']:.2f}\n"
                    f"MACD: {latest['macd']:.2f}, Signal: {latest['macd_signal']:.2f}"
                )
                send_email(f"SELL Alert for {ticker}", message)

        # Show signal
        st.subheader(f"Signal: {signal_text}")

        # Show key indicator values
        st.columns(3)[0].metric("RSI (14)", f"{latest['rsi']:.2f}")
        st.columns(3)[1].metric("MACD", f"{latest['macd']:.2f}")
        st.columns(3)[2].metric("MACD Signal", f"{latest['macd_signal']:.2f}")

        # Charts
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        # Price + SMAs + Volume
        ax1.plot(df['Close'], label='Close Price', color='black')
        ax1.plot(df['sma10'], label='SMA 10', color='blue')
        ax1.plot(df['sma30'], label='SMA 30', color='red')
        ax1.bar(df.index, df['Volume'], color='lightgray', label='Volume', alpha=0.3)
        ax1.set_title(f"{ticker} Price, SMAs, and Volume")
        ax1.legend()

        # RSI
        ax2.plot(df['rsi'], label='RSI (14)', color='purple')
        ax2.axhline(70, color='red', linestyle='--', linewidth=1)
        ax2.axhline(30, color='green', linestyle='--', linewidth=1)
        ax2.set_title("RSI")
        ax2.legend()

        # MACD
        ax3.plot(df['macd'], label='MACD', color='blue')
        ax3.plot(df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, color='black', linewidth=1)
        ax3.set_title("MACD")
        ax3.legend()

        plt.tight_layout()
        st.pyplot(fig)

        with st.expander("📋 View Data"):
            st.dataframe(df.tail(15))

    except Exception as e:
        st.error(f"Something went wrong: {e}")

