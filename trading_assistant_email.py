import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt
import bcrypt
import datetime

# === CONFIG ===
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# === HELPERS ===
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def load_users():
    try:
        return pd.read_csv("users.csv")
    except:
        return pd.DataFrame(columns=["email", "password_hash", "is_admin"])

def is_paid_user(email):
    if not email:
        return False
    try:
        paid = pd.read_csv("paid_users.csv")
        return email in paid["email"].values
    except:
        return False

def log_user_login(email):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.read_csv("logs.csv") if "logs.csv" in os.listdir() else pd.DataFrame(columns=["email", "timestamp"])
    df.loc[len(df)] = [email, now]
    df.to_csv("logs.csv", index=False)

# === EMAIL ALERT ===
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        st.info("📤 Email alert sent.")
    except Exception as e:
        st.error(f"❌ Email error: {e}")

# === STRATEGY ===
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

@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    df.dropna(inplace=True)
    return df

# === LOGIN ===
st.title("🔐 Trading Assistant Login")
users_df = load_users()
email = st.text_input("Email")
password = st.text_input("Password", type="password")
login_button = st.button("Login")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if login_button:
    user = users_df[users_df["email"] == email]
    if not user.empty and check_password(password, user.iloc[0]["password_hash"]):
        if is_paid_user(email):
            st.session_state.authenticated = True
            st.session_state.user_email = email
            log_user_login(email)
            st.success("✅ Login successful!")
        else:
            st.warning("💳 Please complete payment to access.")
    else:
        st.error("❌ Invalid credentials")

# === MAIN APP ===
if st.session_state.get("authenticated"):
    st.subheader("📈 Trading Assistant with Email Alerts")

    ticker = st.text_input("Enter Ticker (e.g. AAPL)", "TSLA")
    interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d"], index=4)
    period_map = {
        "1m": "1d", "5m": "5d", "15m": "5d", "1h": "7d",
        "1d": "3mo"
    }
    period = period_map[interval]

    if ticker:
        df = fetch_data(ticker, period, interval)
        if df.empty:
            st.error("No data found.")
            st.stop()

        df = apply_strategy(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if "last_signal" not in st.session_state:
            st.session_state.last_signal = 0

        if int(latest['signal']) != int(prev['signal']) and int(latest['signal']) != int(st.session_state.last_signal):
            st.session_state.last_signal = int(latest['signal'])
            direction = "BUY" if latest["signal"] == 1 else "SELL"
            body = (
                f"{direction} Signal for {ticker}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}\n"
                f"SMA30: {latest['sma30']:.2f}"
            )
            send_email(f"{direction} Alert for {ticker}", body)

        st.metric("RSI", f"{latest['rsi']:.2f}")
        st.metric("MACD", f"{latest['macd']:.2f}")
        st.metric("Signal", f"{latest['signal']}")

        st.line_chart(df[['Close', 'sma10', 'sma30']].dropna())

        with st.expander("View Raw Data"):
            st.dataframe(df.tail(20))
