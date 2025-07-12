tickers = [t.strip().upper() for t in ticker_input.split(',') if t.strip()]

for ticker in tickers:
    st.subheader(f"📊 {ticker}")
    try:
        df = fetch_data(ticker, period, interval)
        if df.empty:
            st.warning(f"⚠️ No data for {ticker}. Skipping.")
            continue

        df = apply_strategy(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if f"{ticker}_last_signal" not in st.session_state:
            st.session_state[f"{ticker}_last_signal"] = 0

        signal_text = "⚠️ HOLD — No new signal"
        if int(prev['signal']) != int(latest['signal']) and int(latest['signal']) != st.session_state[f"{ticker}_last_signal"]:
            st.session_state[f"{ticker}_last_signal"] = int(latest['signal'])

            message = (
                f"{ticker} Signal: {'BUY' if latest['signal'] == 1 else 'SELL'}\n"
                f"Price: ${latest['Close']:.2f}\n"
                f"RSI: {latest['rsi']:.2f}\n"
                f"MACD: {latest['macd']:.2f}, Signal Line: {latest['macd_signal']:.2f}\n"
                f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
            )

            subject = f"{'BUY' if latest['signal'] == 1 else 'SELL'} Alert: {ticker}"
            send_email(subject, message)
            signal_text = f"{'📈 BUY' if latest['signal'] == 1 else '📉 SELL'} signal at ${latest['Close']:.2f}"

        st.success(f"Signal: {signal_text}")
        
        # Optional: Plotting
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df.index, df['Close'], label='Close', color='black')
        ax.plot(df.index, df['sma10'], label='SMA10', color='blue')
        ax.plot(df.index, df['sma30'], label='SMA30', color='red')
        ax.set_title(f"{ticker} Price with SMAs")
        ax.legend()
        st.pyplot(fig)

        with st.expander("View Data"):
            st.dataframe(df.tail(20))

    except Exception as e:
        st.error(f"❌ Error processing {ticker}: {e}")
