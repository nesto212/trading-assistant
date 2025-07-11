import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load email secrets from Streamlit secrets management
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading Assistant + Email Alerts")

# --- Inputs ---
tickers_input = st.text_input("Enter Tickers (comma separated, e.g. AAPL,TSLA,MSFT):", "TSLA")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)
period_map = {
    "1m": "1d",
    "5m": "5d",
    "15m": "5d",
    "1h": "7d",
    "1d": "1mo",
    "1wk": "3mo",
    "1mo": "1y"
}
period = period_map.get(interval, "1mo")

@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    df.dropna(inplace=True)
    return df

def apply_strategy(df):
    # Validate required columns
    required_cols = {'Close', 'Volume', 'High', 'Low'}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.warning(f"Data missing columns: {missing_cols}. Adding defaults.")
        for col in missing_cols:
            df[col] = 0

    close = df['Close']
    volume = df['Volume']

    # Calculate indicators
    df['rsi'] = ta.momentum.rsi(close=close, window=14)
    macd_indicator = ta.trend.MACD(close=close)
    df['macd'] = macd_indicator.macd()
    df['macd_signal'] = macd_indicator.macd_signal()
    bollinger = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    df['bollinger_upper'] = bollinger.bollinger_hband()
    df['bollinger_lower'] = bollinger.bollinger_lband()
    vwap = ta.volume.VolumeWeightedAveragePrice(
        high=df['High'], low=df['Low'], close=close, volume=volume, window=14)
    df['vwap'] = vwap.volume_weighted_average_price()

    # SMA
    df['sma10'] = ta.trend.sma_indicator(close=close, window=10)
    df['sma30'] = ta.trend.sma_indicator(close=close, window=30)

    # Signals with filters
    buy_cond = (df['sma10'] > df['sma30']) & (df['rsi'] < 70) & (df['macd'] > df['macd_signal'])
    sell_cond = (df['sma10'] < df['sma30']) & (df['rsi'] > 30) & (df['macd'] < df['macd_signal'])
    df['signal'] = 0
    df.loc[buy_cond, 'signal'] = 1
    df.loc[sell_cond, 'signal'] = -1

    df.fillna(0, inplace=True)
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
        st.info(f"📤 Email alert sent: {subject}")
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")

# Session state to track last signals for multiple tickers
if 'last_signals' not in st.session_state:
    st.session_state.last_signals = {}

for ticker in tickers:
    st.header(f"📊 {ticker}")
    try:
        df = fetch_data(ticker, period, interval)
        if df.empty:
            st.warning(f"No data returned for {ticker}. Check ticker or interval.")
            continue

        df = apply_strategy(df)

        if len(df) < 2:
            st.warning(f"Not enough data to generate signals for {ticker}.")
            continue

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        last_signal = st.session_state.last_signals.get(ticker, 0)
        signal_text = "⚠️ HOLD — No new signal"

        if prev['signal'] != latest['signal'] and latest['signal'] != last_signal:
            st.session_state.last_signals[ticker] = latest['signal']

            message = (
                f"Ticker: {ticker}\n"
                f"Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal Line: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}\n"
                f"Bollinger Bands: Upper {latest['bollinger_upper']:.2f}, Lower {latest['bollinger_lower']:.2f}\n"
                f"VWAP: {latest['vwap']:.2f}"
            )

            if latest['signal'] == 1:
                signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
                send_email(f"BUY Alert for {ticker}", message)
            elif latest['signal'] == -1:
                signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"
                send_email(f"SELL Alert for {ticker}", message)

        st.subheader(f"Signal: {signal_text}")

        # Metrics display
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("RSI (14)", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")
        col4.metric("VWAP", f"{latest['vwap']:.2f}")

        # Plot charts
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True,
                                            gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        # Price + SMAs + Bollinger Bands
        ax1.plot(df.index, df['Close'], label='Close Price', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
        ax1.plot(df.index, df['bollinger_upper'], label='Bollinger Upper', color='green', linestyle='--')
        ax1.plot(df.index, df['bollinger_lower'], label='Bollinger Lower', color='green', linestyle='--')
        ax1.bar(df.index, df['Volume'], color='lightgray', alpha=0.3, label='Volume')
        ax1.set_title(f"{ticker} — Price, SMAs & Bollinger Bands")
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

        with st.expander(f"📋 Raw Data for {ticker} (last 20 rows)"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"An error occurred for {ticker}: {e}")
