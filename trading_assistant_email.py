# Assume you've fetched data and applied the strategy, so you have df

latest = df.iloc[-1]
prev = df.iloc[-2]

if 'last_signal' not in st.session_state:
    st.session_state.last_signal = 0

signal_text = "⚠️ HOLD — No new signal"
# Detect signal change and if it’s a new signal not sent before
if int(prev['signal']) != int(latest['signal']) and int(latest['signal']) != int(st.session_state.last_signal):
    st.session_state.last_signal = int(latest['signal'])

    # Prepare message body for email
    message = (
        f"Ticker: {ticker}\n"
        f"Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
        f"Price: ${latest['Close']:.2f}\n"
        f"RSI: {latest['rsi']:.2f}\n"
        f"MACD: {latest['macd']:.2f}\n"
        f"SMA10: {latest['sma10']:.2f}\n"
        f"SMA30: {latest['sma30']:.2f}\n"
    )

    # Send email alert based on signal
    if latest['signal'] == 1:
        subject = f"BUY Alert for {ticker}"
        send_email(subject, message)
        signal_text = f"📈 BUY signal at ${latest['Close']:.2f}"
    elif latest['signal'] == -1:
        subject = f"SELL Alert for {ticker}"
        send_email(subject, message)
        signal_text = f"📉 SELL signal at ${latest['Close']:.2f}"

st.subheader(f"Signal: {signal_text}")
