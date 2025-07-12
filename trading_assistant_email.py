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
    # Precious Metals
    "GC=F": "Gold",
    "SI=F": "Silver",
    "PL=F": "Platinum",
    "PA=F": "Palladium",

    # Energy
    "CL=F": "Crude Oil (WTI)",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "HO=F": "Heating Oil",
    "RB=F": "RBOB Gasoline",

    # Agriculture - Grains & Oilseeds
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
    "ZS=F": "Soybeans",
    "ZL=F": "Soybean Oil",
    "ZM=F": "Soybean Meal",

    # Soft Commodities
    "KC=F": "Coffee",
    "CC=F": "Cocoa",
    "SB=F": "Sugar #11",
    "CT=F": "Cotton",

    # Livestock
    "LE=F": "Live Cattle",
    "HE=F": "Lean Hogs",

    # Base Metals
    "HG=F": "Copper",

    # Other
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

# Prepare options for dropdowns
commodity_options = [f"{name} ({ticker})" for ticker, name in commodities.items()]
forex_options = [f"{name} ({ticker})" for ticker, name in forex.items()]

# Select category
category = st.radio("Select Category:", ["Stocks", "Commodities", "Forex"])

if category == "Stocks":
    ticker = st.selectbox(f"Select {category} Ticker:", stocks)
elif category == "Commodities":
    selected = st.selectbox(f"Select {category} Ticker:", commodity_options)
    ticker = selected.split("(")[-1].strip(")")
else:  # Forex
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

def fibonacci_levels(df):
    max_price = df['Close'].max()
    min_price = df['Close'].min()
    diff = max_price - min_price

    levels = {
        "level_0": max_price,
        "level_236": max_price - 0.236 * diff,
        "level_382": max_price - 0.382 * diff,
        "level_5": max_price - 0.5 * diff,
        "level_618": max_price - 0.618 * diff,
        "level_786": max_price - 0.786 * diff,
        "level_1": min_price
    }
    return levels

def apply_strategy(df):
    required_cols = {'Close', 'Volume', 'High', 'Low'}
    if not required_cols.issubset(df.columns):
        st.warning(f"Data missing required columns: {required_cols}")
        return None, None
    
    df = df.dropna(subset=required_cols)
    
    # Existing indicators
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    # Bollinger Bands (20-period, 2 std)
    bb_indicator = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['bb_upper'] = bb_indicator.bollinger_hband()
    df['bb_lower'] = bb_indicator.bollinger_lband()
    df['bb_middle'] = bb_indicator.bollinger_mavg()
    
    # Stochastic Oscillator (%K and %D)
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'], window=14, smooth_window=3)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    
    # Fibonacci levels
    levels = fibonacci_levels(df)
    threshold = 0.01

    def near_fib_levels(price):
        for level_price in levels.values():
            if abs(price - level_price) / price < threshold:
                return True
        return False

    df['signal'] = 0
    for i in range(1, len(df)):
        prev_sma10 = df['sma10'].iloc[i-1]
        prev_sma30 = df['sma30'].iloc[i-1]
        curr_sma10 = df['sma10'].iloc[i]
        curr_sma30 = df['sma30'].iloc[i]
        price = df['Close'].iloc[i]
        rsi = df['rsi'].iloc[i]
        stoch_k = df['stoch_k'].iloc[i]
        stoch_d = df['stoch_d'].iloc[i]
        bb_lower = df['bb_lower'].iloc[i]
        bb_upper = df['bb_upper'].iloc[i]

        # SMA crossover condition
        sma_buy = (prev_sma10 <= prev_sma30) and (curr_sma10 > curr_sma30)
        sma_sell = (prev_sma10 >= prev_sma30) and (curr_sma10 < curr_sma30)

        # Bollinger confirmation: price near lower band for buy, upper band for sell
        bb_buy = price <= bb_lower * 1.01
        bb_sell = price >= bb_upper * 0.99

        # Stochastic confirmation: oversold for buy, overbought for sell
        stoch_buy = stoch_k < 20 and stoch_d < 20 and stoch_k > stoch_d  # %K crossing above %D in oversold zone
        stoch_sell = stoch_k > 80 and stoch_d > 80 and stoch_k < stoch_d  # %K crossing below %D in overbought zone

        # Fibonacci confirmation
        fib_confirm = near_fib_levels(price)

        if sma_buy and bb_buy and stoch_buy and fib_confirm:
            df.at[df.index[i], 'signal'] = 1
        elif sma_sell and bb_sell and stoch_sell and fib_confirm:
            df.at[df.index[i], 'signal'] = -1
        else:
            df.at[df.index[i], 'signal'] = df['signal'].iloc[i-1]

    return df, levels

if ticker:
    df = fetch_data(ticker, period, interval)
    if df.empty:
        st.warning("⚠️ No data returned. Try changing ticker, interval, or period.")
        st.stop()
    required_cols = {'Close', 'Volume', 'High', 'Low'}
    if not required_cols.issubset(df.columns):
        st.warning(f"⚠️ Data missing columns {required_cols}. Try a longer period or lower frequency interval.")
        st.stop()

    df, fib_levels = apply_strategy(df)
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
            f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}\n"
            f"Bollinger Bands - Upper: {latest['bb_upper']:.2f}, Lower: {latest['bb_lower']:.2f}\n"
            f"Stochastic %K: {latest['stoch_k']:.2f}, %D: {latest['stoch_d']:.2f}"
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

    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 16), sharex=True,
                                             gridspec_kw={'height_ratios': [3, 1.2, 1.2, 1.2]})

    # Price + SMAs + Volume + Bollinger Bands
    ax1.plot(df.index, df['Close'], label='Close Price', color='black')
    ax1.plot(df.index, df['sma10'], label='SMA 10', color='blue')
    ax1.plot(df.index, df['sma30'], label='SMA 30', color='red')
    ax1.plot(df.index, df['bb_upper'], label='BB Upper', linestyle='--', color='cyan')
    ax1.plot(df.index, df['bb_middle'], label='BB Middle', linestyle='--', color='gray')
    ax1.plot(df.index, df['bb_lower'], label='BB Lower', linestyle='--', color='cyan')
    ax1.bar(df.index, df['Volume'], color='lightgray', alpha=0.3, label='Volume')
    ax1.set_title(f"{ticker} — Price, SMAs & Bollinger Bands")
    ax1.legend()

    # RSI
    ax2.plot(df.index, df['rsi'], label='RSI (14)', color='purple')
    ax2.axhline(70, linestyle='--', color='red')
    ax2.axhline(30, linestyle='--', color='green')
    ax2.set_title("Relative Strength Index")
    ax2.legend()

    # MACD
    ax3.plot(df.index, df['macd'], label='MACD', color='blue')
    ax3.plot(df.index, df['macd_signal'], label='Signal Line', color='red')
    ax3.set_title("MACD")
    ax3.legend()

    # Stochastic Oscillator
    ax4.plot(df.index, df['stoch_k'], label='%K', color='magenta')
    ax4.plot(df.index, df['stoch_d'], label='%D', color='orange')
    ax4.axhline(80, linestyle='--', color='red')
    ax4.axhline(20, linestyle='--', color='green')
    ax4.set_title("Stochastic Oscillator")
    ax4.legend()

    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

    # Show Fibonacci levels info
    st.markdown("### Fibonacci Levels:")
    for level, price in fib_levels.items():
        st.write(f"{level}: {price:.2f}")
