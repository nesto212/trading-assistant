import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# --- Secrets and Config ---
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- Streamlit Setup ---
st.set_page_config(page_title="Trading Assistant", layout="wide")

class TradingAssistant:
    def __init__(self, ticker, interval, fallback_enabled=True, fallback_ticker="AAPL"):
        self.ticker = ticker
        self.interval = interval
        self.period_map = {
            "1m": "1d", "5m": "5d", "15m": "5d",
            "1h": "7d", "1d": "1mo"
        }
        self.intervals_fallback = ["5m", "15m", "1h", "1d"]
        self.period = self.period_map.get(interval, "5d")
        self.df = pd.DataFrame()
        self.fallback_enabled = fallback_enabled
        self.fallback_ticker = fallback_ticker

    @st.cache_data(ttl=300)
    def fetch_data(self, ticker, period, interval):
        df = yf.download(ticker, period=period, interval=interval)
        return df

    def get_data_with_fallback(self):
        df = self.fetch_data(self.ticker, self.period, self.interval)
        if not self.valid_data(df):
            st.warning(f"⚠️ Primary data for {self.ticker} failed. Attempting fallback...")

            if self.fallback_enabled:
                fallback_df = self.fetch_data(self.fallback_ticker, "5d", "5m")
                if self.valid_data(fallback_df):
                    st.info(f"✅ Using fallback ticker: {self.fallback_ticker}")
                    self.ticker = self.fallback_ticker
                    self.df = fallback_df
                    return
                else:
                    st.error(f"❌ Fallback ticker {self.fallback_ticker} also failed.")
                    st.stop()
            else:
                st.error("❌ Invalid data and fallback is disabled.")
                st.stop()

        self.df = df

    def valid_data(self, df):
        required = {'Close', 'Volume'}
        return not df.empty and required.issubset(df.columns)

    def apply_strategy(self):
        close = self.df['Close']
        volume = self.df['Volume']

        self.df['sma10'] = ta.trend.sma_indicator(close, window=10)
        self.df['sma30'] = ta.trend.sma_indicator(close, window=30)
        self.df['rsi'] = ta.momentum.rsi(close, window=14)

        macd = ta.trend.MACD(close)
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()

        self.df['signal'] = 0
        self.df.loc[self.df['sma10'] > self.df['sma30'], 'signal'] = 1
        self.df.loc[self.df['sma10'] < self.df['sma30'], 'signal'] = -1

    def send_email(self, subject, body):
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
            st.error(f"❌ Email failed: {e}")

    def plot_charts(self):
        latest = self.df.iloc[-1]

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2]})

        ax1.plot(self.df.index, self.df['Close'], label='Close', color='black')
        ax1.plot(self.df.index, self.df['sma10'], label='SMA10', color='blue')
        ax1.plot(self.df.index, self.df['sma30'], label='SMA30', color='red')
        ax1.bar(self.df.index, self.df['Volume'], color='gray', alpha=0.3, label='Volume')
        ax1.set_title(f"{self.ticker} — Price & SMAs")
        ax1.legend()

        ax2.plot(self.df.index, self.df['rsi'], label='RSI (14)', color='purple')
        ax2.axhline(70, linestyle='--', color='red')
        ax2.axhline(30, linestyle='--', color='green')
        ax2.set_title("RSI")
        ax2.legend()

        ax3.plot(self.df.index, self.df['macd'], label='MACD', color='blue')
        ax3.plot(self.df.index, self.df['macd_signal'], label='Signal Line', color='orange')
        ax3.axhline(0, linestyle='--', color='black')
        ax3.set_title("MACD")
        ax3.legend()

        plt.tight_layout()
        st.pyplot(fig)

    def run_signal_alert(self):
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal_text = "⚠️ HOLD — No new signal"
        if prev['signal'] != latest['signal'] and latest['signal'] != st.session_state.last_signal:
            st.session_state.last_signal = latest['signal']
            action = 'BUY' if latest['signal'] == 1 else 'SELL'
            signal_text = f"{'📈' if action == 'BUY' else '📉'} {action} signal at ${latest['Close']:.2f}"

            message = (
                f"Signal: {action}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
            )
            self.send_email(f"{action} Alert for {self.ticker}", message)

        st.subheader(f"Signal: {signal_text}")
        col1, col2, col3 = st.columns(3)
        col1.metric("RSI", f"{latest['rsi']:.2f}")
        col2.metric("MACD", f"{latest['macd']:.2f}")
        col3.metric("Signal Line", f"{latest['macd_signal']:.2f}")

        with st.expander("📋 Raw Data"):
            st.dataframe(self.df.tail(20))


# --- UI Inputs ---
st.title("📊 Trading Assistant + Email Alerts")

ticker = st.text_input("Enter Ticker:", "TSLA")
interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=1)

with st.sidebar:
    fallback_enabled = st.checkbox("🔄 Enable Fallback if Data Fails", value=True)
    fallback_ticker = st.text_input("Fallback Ticker", "AAPL")

# --- Run Assistant ---
assistant = TradingAssistant(ticker, interval, fallback_enabled, fallback_ticker)
assistant.get_data_with_fallback()
assistant.apply_strategy()
assistant.run_signal_alert()
assistant.plot_charts()
