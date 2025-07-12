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
    if signal == 1:
        sl = entry_price - atr_multiplier * atr
        tp = entry_price + risk_reward * (entry_price - sl)
    elif signal == -1:
        sl = entry_price + atr_multiplier * atr
        tp = entry_price - risk_reward * (sl - entry_price)
    else:
        sl, tp = None, None
    return sl, tp

def scan_instruments(tickers, period, interval):
    results = []
    for symbol in tickers:
        df = fetch_data(symbol, period, interval)
        df = apply_strategy(df)
        if df is None or df.empty:
            continue
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        if int(prev['signal']) != int(latest['signal']):
            results.append({
                "Ticker": symbol,
                "Signal": "BUY" if latest['signal'] == 1 else "SELL",
                "Price": latest['Close'],
                "RSI": latest['rsi']
            })
    return results

if st.checkbox("🔄 Auto-Scan Top Instruments"):
    if category == "Stocks":
        tickers_to_scan = stocks
    elif category == "Commodities":
        tickers_to_scan = list(commodities.keys())
    else:
        tickers_to_scan = list(forex.keys())

    scan_results = scan_instruments(tickers_to_scan, period, interval)

    if scan_results:
        st.write(f"### Top {len(scan_results)} trading opportunities:")
        for res in scan_results:
            st.markdown(f"**{res['Ticker']}** | Signal: {res['Signal']} | Price: ${res['Price']:.2f} | RSI: {res['RSI']:.1f}")

        if st.button("Generate Charts for Scanner Results"):
            for res in scan_results:
                ticker = res['Ticker']
                st.subheader(f"Charts & Signals for {ticker}")
                df = fetch_data(ticker, period, interval)
                df = apply_strategy(df)
                if df is None or len(df) < 35:
                    st.warning(f"Not enough data for {ticker}")
                    continue
                latest = df.iloc[-1]
                signal = latest['signal']
                sl, tp = calculate_tp_sl(latest, latest['atr'], signal)

                st.markdown(f"**Signal:** {'BUY' if signal == 1 else 'SELL' if signal == -1 else 'HOLD'}")
                st.markdown(f"**Price:** ${latest['Close']:.2f} | **RSI:** {latest['rsi']:.1f}")
                st.markdown(f"**TP:** ${tp:.2f} | **SL:** ${sl:.2f}")

                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(df.index, df['Close'], label='Close', color='black')
                ax.plot(df.index, df['sma10'], label='SMA10', color='blue')
                ax.plot(df.index, df['sma30'], label='SMA30', color='red')
                if sl and tp:
                    ax.axhline(sl, color='red', linestyle='--', label='SL')
                    ax.axhline(tp, color='green', linestyle='--', label='TP')
                ax.legend()
                st.pyplot(fig)
    else:
        st.warning("No strong signals found.")
else:
    st.info("📊 Manual analysis mode enabled.")
    if ticker:
        df = fetch_data(ticker, period, interval)
        if df.empty:
            st.warning("No data found. Try a different selection.")
            st.stop()
        df = apply_strategy(df)
        if df is None:
            st.warning("Failed to apply strategy.")
            st.stop()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if 'last_signal' not in st.session_state:
            st.session_state.last_signal = 0

        signal = int(latest['signal'])
        signal_text = "⚠️ HOLD"
        if int(prev['signal']) != signal and signal != st.session_state.last_signal:
            st.session_state.last_signal = signal
            signal_text = f"{'📈 BUY' if signal == 1 else '📉 SELL'} signal at ${latest['Close']:.2f}"
            msg = f"Signal: {signal_text}\nPrice: {latest['Close']}\nRSI: {latest['rsi']}"
            send_email(f"{signal_text} Alert - {ticker}", msg)

        st.subheader(f"Signal: {signal_text}")
        sl, tp = calculate_tp_sl(latest, latest['atr'], signal)
        st.markdown(f"**TP:** ${tp:.2f} | **SL:** ${sl:.2f}")

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df.index, df['Close'], label='Close', color='black')
        ax.plot(df.index, df['sma10'], label='SMA10', color='blue')
        ax.plot(df.index, df['sma30'], label='SMA30', color='red')
        if sl and tp:
            ax.axhline(sl, color='red', linestyle='--', label='SL')
            ax.axhline(tp, color='green', linestyle='--', label='TP')
        ax.legend()
        st.pyplot(fig)
