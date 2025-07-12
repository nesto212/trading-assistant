def scan():
    all_tickers = stocks + list(commodities.keys()) + list(forex.keys())

    for ticker in all_tickers:
        df = fetch_data(ticker)
        if df.empty:
            continue

        df = apply_strategy(df)
        if df is None or len(df) < 2:
            continue

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        signal = int(latest['signal'])

        if signal != 0 and signal != int(prev['signal']):
            if is_strong_signal(latest, signal):
                direction = "BUY" if signal == 1 else "SELL"
                message = (
                    f"💥 STRONG {direction} SIGNAL for {ticker}\n"
                    f"Price: ${latest['Close']:.2f}\n"
                    f"RSI: {latest['rsi']:.2f}\n"
                    f"MACD: {latest['macd']:.2f} vs Signal: {latest['macd_signal']:.2f}\n"
                    f"SMA10: {latest['sma10']:.2f}, SMA30: {latest['sma30']:.2f}"
                )
                send_email(f"⚠️ STRONG {direction} Alert for {ticker}", message)
