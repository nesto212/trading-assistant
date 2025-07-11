import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load email credentials
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="📈 Multi-Ticker Trading Assistant", layout="wide")
st.title("📧 Multi-Ticker Trading Assistant + Email Alerts")

# Input: Multiple tickers
tickers_input = st.text_input("Enter tickers (comma separated, e.g. AAPL, TSLA, NVDA):", "AAPL, TSLA")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)
period_map = {
    "1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d",
    "1d": "3mo", "1wk": "6mo", "1mo": "1y"
}
period = period_map[interval]

# Cache fetch
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# Send email
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
        st.info(f"📤 Email alert sent: {subject}")
    except Exception as e:
        st.error(f"❌ Email failed: {e}")

# Strategy
def apply_strategy(df):
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1
    return df

# Track state
if "signal_state" not in st.session_state:
    st.session_state.signal_state = {}

# Analyze each ticker
for ticker in tickers:
    st.subheader(f"📊 {ticker}")

    try:
        df = fetch_data(ticker, period, interval)
        if df.empty or len(df) < 2:
            st.warning(f"{ticker}: Not enough data.")
            continue

        df = apply_strategy(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if ticker not in st.session_state.signal_state:
            st.session_state.signal_state[ticker] = 0

        signal_text = "HOLD"

        if int(prev['signal']) != int(latest['signal']) and int(latest['signal']) != st.session_state.signal_state[ticker]:
            st.session_state.signal_state[ticker] = int(latest['signal'])

            message = (
                f"Ticker: {ticker}\n"
                f"Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal Line: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
            )

            signal_type = "BUY" if latest['signal'] == 1 else "SELL"
            send_email(f"{signal_type} Signal: {ticker}", message)
            signal_text = f"📈 {signal_type}"

        st.markdown(f"**Signal:** {signal_text} | **Close:** ${latest['Close']:.2f}")

        # Plotting
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        ax1.plot(df.index, df['Close'], label='Close', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA30', color='red')
        ax1.set_title(f"{ticker} — Price & SMAs")
        ax1.legend()

        ax2.plot(df.index, df['rsi'], label='RSI', color='purple')
        ax2.axhline(70, color='red', linestyle='--')
        ax2.axhline(30, color='green', linestyle='--')
        ax2.set_title("RSI")
        ax2.legend()

        ax3.plot(df.index, df['macd'], label='MACD', color='blue')
        ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, color='black', linestyle='--')
        ax3.set_title("MACD")
        ax3.legend()

        st.pyplot(fig)
        st.dataframe(df.tail(10))

    except Exception as e:
        st.error(f"{ticker}: {e}")
