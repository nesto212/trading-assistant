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

st.set_page_config(page_title="Multi-Ticker Trading Assistant", layout="wide")
st.title("📊 Multi-Ticker Trading Assistant + Email Alerts")

# User input
user_input = st.text_input("Enter Tickers (comma-separated, e.g. AAPL, TSLA, NVDA):", "TSLA, AAPL")
tickers = [x.strip().upper() for x in user_input.split(",") if x.strip()]
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=1)
period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d", "1d": "1mo"}
period = period_map[interval]

@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

def apply_strategy(df):
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()

    if {'High', 'Low', 'Close', 'Volume'}.issubset(df.columns):
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            volume=df['Volume']
        ).vwap()
    else:
        df['vwap'] = pd.NA

    df['signal'] = 0
    for i in range(1, len(df)):
        if (
            df['sma10'].iloc[i] > df['sma30'].iloc[i] and
            df['sma10'].iloc[i - 1] <= df['sma30'].iloc[i - 1] and
            df['rsi'].iloc[i] < 30 and
            df['macd'].iloc[i - 1] < df['macd_signal'].iloc[i - 1] and
            df['macd'].iloc[i] > df['macd_signal'].iloc[i]
        ):
            df.at[df.index[i], 'signal'] = 1
        elif (
            df['sma10'].iloc[i] < df['sma30'].iloc[i] and
            df['sma10'].iloc[i - 1] >= df['sma30'].iloc[i - 1] and
            df['rsi'].iloc[i] > 70 and
            df['macd'].iloc[i - 1] > df['macd_signal'].iloc[i - 1] and
            df['macd'].iloc[i] < df['macd_signal'].iloc[i]
        ):
            df.at[df.index[i], 'signal'] = -1

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

for ticker in tickers:
    st.subheader(f"📈 {ticker} Analysis")
    try:
        df = fetch_data(ticker, period, interval)
        if df.empty:
            st.warning(f"⚠️ No data for {ticker}.")
            continue

        df = apply_strategy(df)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if f"last_signal_{ticker}" not in st.session_state:
            st.session_state[f"last_signal_{ticker}"] = 0

        signal_text = "⚠️ HOLD"
        if prev['signal'] != latest['signal'] and latest['signal'] != st.session_state[f"last_signal_{ticker}"]:
            st.session_state[f"last_signal_{ticker}"] = latest['signal']

            message = (
                f"Ticker: {ticker}\nSignal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Price: ${latest['Close']:.2f}\nRSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal Line: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
            )

            signal_text = f"{'📈 BUY' if latest['signal'] == 1 else '📉 SELL'} signal at ${latest['Close']:.2f}"
            send_email(f"{ticker} Trading Alert", message)

        st.markdown(f"### Signal: {signal_text}")

        col1, col2, col3 = st.columns(3)
        col1.metric("RSI (14)", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        ax1.plot(df.index, df['Close'], label='Close', color='black')
        ax1.plot(df.index, df['sma10'], label='SMA10', color='blue')
        ax1.plot(df.index, df['sma30'], label='SMA30', color='red')
        ax1.plot(df.index, df['bb_upper'], '--', color='grey', alpha=0.3, label='BB Upper')
        ax1.plot(df.index, df['bb_middle'], '--', color='grey', alpha=0.3, label='BB Middle')
        ax1.plot(df.index, df['bb_lower'], '--', color='grey', alpha=0.3, label='BB Lower')
        if df['vwap'].notna().all():
            ax1.plot(df.index, df['vwap'], label='VWAP', linestyle='--', color='orange')
        ax1.legend()
        ax1.set_title("Price with SMAs, BB, VWAP")

        ax2.plot(df.index, df['rsi'], label='RSI', color='purple')
        ax2.axhline(70, linestyle='--', color='red')
        ax2.axhline(30, linestyle='--', color='green')
        ax2.set_title("RSI")
        ax2.legend()

        ax3.plot(df.index, df['macd'], label='MACD', color='blue')
        ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, linestyle='--', color='black')
        ax3.set_title("MACD")
        ax3.legend()

        st.pyplot(fig)

        with st.expander("📋 View Raw Data"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"An error occurred for {ticker}: {e}")
