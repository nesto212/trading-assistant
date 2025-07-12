import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt
import hashlib
import hmac
import os
import base64

# -------- Password hashing utils --------
def hash_password(password: str, salt: bytes = None) -> (str, str):
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hash_b64 = base64.b64encode(hashed).decode('utf-8')
    return salt_b64, hash_b64

def verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    salt = base64.b64decode(salt_b64.encode('utf-8'))
    expected_hash = base64.b64decode(hash_b64.encode('utf-8'))
    test_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return hmac.compare_digest(test_hash, expected_hash)

# -------- Email config --------
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# -------- User store --------
# In-memory user store: username -> {salt, hash}
if 'users' not in st.session_state:
    st.session_state.users = {}

# -------- Session state --------
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# -------- Functions --------
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

@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

def apply_strategy(df):
    if not {'Close', 'Volume'}.issubset(df.columns):
        st.warning("Data missing required columns 'Close' and/or 'Volume'.")
        df['signal'] = 0
        return df

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

def register_user():
    st.subheader("Register")
    username = st.text_input("Username", key="reg_username")
    password = st.text_input("Password", type="password", key="reg_password")
    if st.button("Register", key="reg_button"):
        if not username or not password:
            st.error("Please enter both username and password.")
            return
        if username in st.session_state.users:
            st.error("Username already exists.")
        else:
            salt, hashed = hash_password(password)
            st.session_state.users[username] = {'salt': salt, 'hash': hashed}
            st.success("User registered! Please login.")

def login_user():
    st.subheader("Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        user = st.session_state.users.get(username)
        if user and verify_password(password, user['salt'], user['hash']):
            st.session_state.logged_in_user = username
            st.success(f"Welcome back, {username}!")
        else:
            st.error("Invalid username or password.")

def trading_assistant():
    st.title(f"📈 Trading Assistant - User: {st.session_state.logged_in_user}")

    ticker = st.text_input("Enter Ticker (e.g. AAPL, TSLA):", "TSLA")
    interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)
    period_map = {
        "1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d",
        "1d": "3mo", "1wk": "6mo", "1mo": "1y"
    }
    period = period_map[interval]

    if ticker:
        try:
            df = fetch_data(ticker, period, interval)
            if df.empty or len(df) < 2:
                st.warning("⚠️ No or insufficient data. Check ticker or interval.")
                return

            df = apply_strategy(df)

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            if 'last_signal' not in st.session_state:
                st.session_state.last_signal = 0

            signal_text = "⚠️ HOLD — No new signal"
            if int(prev['signal']) != int(latest['signal']) and int(latest['signal']) != int(st.session_state.last_signal):
                st.session_state.last_signal = int(latest['signal'])

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

def logout():
    st.session_state.logged_in_user = None
    st.session_state.last_signal = 0
    st.success("Logged out.")

# -------- Main --------
st.set_page_config(page_title="Trading Assistant with Secure Login", layout="wide")

st.title("🔒 Secure Trading Assistant with Email Alerts")

if st.session_state.logged_in_user:
    st.sidebar.write(f"Logged in as: {st.session_state.logged_in_user}")
    if st.sidebar.button("Logout"):
        logout()
    trading_assistant()
else:
    choice = st.sidebar.radio("Choose:", ["Login", "Register"])
    if choice == "Login":
        login_user()
    else:
        register_user()
