import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt

# Email secrets
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="Trading Assistant with Alerts", layout="wide")
st.title("📧 Trading Assistant + Email Alerts")

# Stocks list
stocks = ["AAPL", "TSLA", "AMZN", "GOOGL", "MSFT", "NFLX", "NVDA", "META", "BABA", "INTC"]

# Commodities with full names
commodities = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "PL=F": "Platinum",
    "PA=F": "Palladium",
    "CL=F": "Crude Oil (WTI)",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "HO=F": "Heating Oil",
    "RB=F": "RBOB Gasoline",
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
    "ZS=F": "Soybeans",
    "ZL=F": "Soybean Oil",
    "ZM=F": "Soybean Meal",
    "KC=F": "Coffee",
    "CC=F": "Cocoa",
    "SB=F": "Sugar #11",
    "CT=F": "Cotton",
    "LE=F": "Live Cattle",
    "HE=F": "Lean Hogs",
    "HG=F": "Copper",
    "QC=F": "Canadian Dollar",
    "DX=F": "US Dollar Index"
}

# Forex pairs with full names
forex = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "USDCHF=X": "USD/CHF",
    "NZDUSD=X": "NZD/USD"
}

commodity_options = [f"{name} ({ticker})" for ticker, name in commodities.items()]
forex_options = [f"{name} ({ticker})" for ticker, name in forex.items()]

category = st.radio("Select Category:", ["Stocks", "Commodities", "Forex"])

if category == "Stocks":
    ticker = st.selectbox(f"Select {category} Ticker:", stocks)
elif category == "Commodities":
    selected = st.selectbox(f"Select {category} Ticker:", commodity_options)
    ticker = selected.split("(")[-1].strip(")")
else:
    selected = st.selectbox(f"Select {category} Pair:", forex_options)
    ticker = selected.split("(")[-1].strip(")")

interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"], index=4)

period_map = {
    "1m": "5d",
    "5m": "5d",
    "15m": "5d",
    "1h": "1mo",
    "1d": "3mo",
    "1wk": "6mo",
    "1mo": "1y"
}

period = period_map[interval]

@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
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

def apply_strategy(df):
    if not {'Close', 'Volume', 'High', 'Low'}.issubset(df.columns):
        return None
    
    df = df.dropna(subset=['Close', 'Volume', 'High', 'Low'])
    if len(df) < 35:
        return None

    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    df['atr'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'], window=14, smooth_window=3)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()

    df['adx'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)

    df['vol_ma'] = df['Volume'].rolling(window=20).mean()

    df['signal'] = 0
    df.loc[df['sma10'] > df['sma30'], 'signal'] = 1
    df.loc[df['sma10'] < df['sma30'], 'signal'] = -1

    return df

def calculate_tp_sl(latest, atr, signal, risk_reward=2.0, atr_multiplier=1.5):
    entry_price = latest['Close']
    sl = None
    tp = None
    
    if signal == 1:  # BUY
        sl = entry_price - atr_multiplier * atr
        tp = entry_price + risk_reward * (entry_price - sl)
    elif signal == -1:  # SELL
        sl = entry_price + atr_multiplier * atr
        tp = entry_price - risk_reward * (sl - entry_price)
    
    return sl, tp

if ticker:
    df = fetch_data(ticker, period, interval)
    if df.empty:
        st.warning("⚠️ No data returned. Try changing ticker, interval, or period.")
        st.stop()
    if not {'Close', 'Volume', 'High', 'Low'}.issubset(df.columns):
        st.warning("⚠️ Data missing 'Close', 'Volume', 'High', or 'Low'. Try a longer period or lower frequency interval.")
        st.stop()

    df = apply_strategy(df)
    if df is None:
        st.stop()

    if len(df) < 35:
        st.warning("⚠️ Not enough data points for indicators (need at least 35). Try a longer period.")
        st.stop()

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

    # Calculate and show TP/SL
    if latest['atr'] > 0 and latest['signal'] != 0:
        sl, tp = calculate_tp_sl(latest, latest['atr'], latest['signal'])
        st.markdown(f"**Take Profit:** ${tp:.2f}  |  **Stop Loss:** ${sl:.2f}")
    else:
        sl, tp = None, None
        st.markdown("**Take Profit:** N/A  |  **Stop Loss:** N/A")

    fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(14, 18), sharex=True,
                                                 gridspec_kw={'height_ratios': [3, 1.2, 1.2, 1, 1]})

    ax1.plot(df.index, df['Close'], label='Close Price', color='black')
    ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
    ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
    ax1.bar(df.index, df['Volume'], color='lightgray', alpha=0.3, label='Volume')
    ax1.set_title(f"{ticker} — Price & SMAs")

    # Plot TP/SL lines if available
    if sl is not None and tp is not None:
        ax1.axhline(sl, color='red', linestyle='--', linewidth=1.5, label='Stop Loss')
        ax1.axhline(tp, color='green', linestyle='--', linewidth=1.5, label='Take Profit')

    ax1.legend(loc='upper left')

    ax2.plot(df.index, df['rsi'], label='RSI', color='purple')
    ax2.axhline(70, color='red', linestyle='--')
    ax2.axhline(30, color='green', linestyle='--')
    ax2.set_title("RSI")
    ax2.legend()

    ax3.plot(df.index, df['macd'], label='MACD', color='blue')
    ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='orange')
    ax3.set_title("MACD")
    ax3.legend()

    ax4.plot(df.index, df['stoch_k'], label='%K', color='green')
    ax4.plot(df.index, df['stoch_d'], label='%D', color='red')
    ax4.axhline(80, color='red', linestyle='--')
    ax4.axhline(20, color='green', linestyle='--')
    ax4.set_title("Stochastic Oscillator")
    ax4.legend()

    ax5.plot(df.index, df['adx'], label='ADX', color='brown')
    ax5.axhline(25, color='blue', linestyle='--')
    ax5.set_title("ADX")
    ax5.legend()

    plt.tight_layout()
    st.pyplot(fig)
