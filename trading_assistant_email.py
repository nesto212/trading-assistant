def apply_strategy(df):
    df['sma10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['sma30'] = ta.trend.sma_indicator(df['Close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()

    # VWAP (Note: VWAP requires intraday data and volume)
    if {'High', 'Low', 'Close', 'Volume'}.issubset(df.columns):
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            volume=df['Volume']
        ).vwap()
    else:
        df['vwap'] = pd.NA

    # Signal logic with RSI and MACD filters
    df['signal'] = 0

    for i in range(1, len(df)):
        # BUY
        if (
            df['sma10'].iloc[i] > df['sma30'].iloc[i] and
            df['sma10'].iloc[i - 1] <= df['sma30'].iloc[i - 1] and
            df['rsi'].iloc[i] < 30 and
            df['macd'].iloc[i - 1] < df['macd_signal'].iloc[i - 1] and
            df['macd'].iloc[i] > df['macd_signal'].iloc[i]
        ):
            df.at[df.index[i], 'signal'] = 1

        # SELL
        elif (
            df['sma10'].iloc[i] < df['sma30'].iloc[i] and
            df['sma10'].iloc[i - 1] >= df['sma30'].iloc[i - 1] and
            df['rsi'].iloc[i] > 70 and
            df['macd'].iloc[i - 1] > df['macd_signal'].iloc[i - 1] and
            df['macd'].iloc[i] < df['macd_signal'].iloc[i]
        ):
            df.at[df.index[i], 'signal'] = -1

    return df
