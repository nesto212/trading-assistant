import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Load email secrets
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading 212 Assistant + Email Alerts")

# User inputs
ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)
period_map = {
    "1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d",
    "1d": "3mo", "1wk": "6mo", "1mo": "1y"
}
period = period_map[interval]

# Cache data fetch
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# Email sender
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

# Strategy logic with safe indicator calculation
def apply_strategy(df):
    required_cols = {'Close', 'Volume'}
    if not required_cols.issubset(df.columns):
        st.warning(f"Data missing required columns {required_cols}.")
        df['signal'] = 0
        return df

    try:
        df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
        df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
        df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

        macd = ta.trend.MACD(df['Close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        df['volume_ma'] = ta.trend.sma_indicator(df['Volume'], window=20)
    except Exception as e:
        st.error(f"Failed to calculate indicators: {e}")
        # Create empty indicator columns if calculation fails
        for col in ['sma10', 'sma30', 'rsi', 'macd', 'macd_signal', 'volume_ma']:
            if col not in df.columns:
                df[col] = float('nan')

    df['signal'] = 0
    # Only assign signals if SMA columns have no NaN (enough data)
    if df['sma10'].notna().all() and df['sma30'].notna().all():
        df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
        df.loc[df['sma10'] < df['sma30'], 'signal'] = -1

    return df

def safe_float(val):
    try:
        return float(val)
    except:
        return float('nan')

# Main logic
if ticker:
    try:
        df = fetch_data(ticker, period, interval)
        if df.empty or len(df) < 30:
            st.warning("⚠️ No or insufficient data for indicators. Need at least 30 data points.")
            st.stop()

        df = apply_strategy(df)
        st.write("Indicator columns available:", [col for col in df.columns if col in ['sma10', 'sma30', 'rsi', 'macd', 'macd_signal']])

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        latest_signal = int(latest.get('signal', 0))
        prev_signal = int(prev.get('signal', 0))

        if prev_signal != latest_signal and latest_signal != st.session_state.last_signal and latest_signal != 0:
            st.session_state.last_signal = latest_signal

            message = (
                f"Signal: {'BUY' if latest_signal == 1 else 'SELL'}\n"
                f"Price: ${safe_float(latest.get('Close', 0)):.2f}\n"
                f"RSI: {safe_float(latest.get('rsi', float('nan'))):.2f}\n"
                f"MACD: {safe_float(latest.get('macd', float('nan'))):.2f}, "
                f"Signal Line: {safe_float(latest.get('macd_signal', float('nan'))):.2f}\n"
                f"SMA10: {safe_float(latest.get('sma10', float('nan'))):.2f}, "
                f"SMA30: {safe_float(latest.get('sma30', float('nan'))):.2f}"
            )

            if latest_signal == 1:
                signal_text = f"📈 BUY signal at ${safe_float(latest.get('Close', 0)):.2f}"
                send_email(f"BUY Alert for {ticker}", message)
            elif latest_signal == -1:
                signal_text = f"📉 SELL signal at ${safe_float(latest.get('Close', 0)):.2f}"
                send_email(f"SELL Alert for {ticker}", message)

        st.subheader(f"Signal: {signal_text}")

        col1, col2, col3 = st.columns(3)
        col1.metric("RSI (14)", f"{safe_float(latest.get('rsi', float('nan'))):.2f}")
        col2.metric("MACD", f"{safe_float(latest.get('macd', float('nan'))):.2f}")
        col3.metric("Signal Line", f"{safe_float(latest.get('macd_signal', float('nan'))):.2f}")

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
