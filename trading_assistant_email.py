if len(df) < 2 or 'signal' not in df.columns:
    st.warning("Not enough data or missing signal column to generate alerts.")
    st.stop()

latest = df.iloc[-1]
prev = df.iloc[-2]

prev_signal = prev['signal']
latest_signal = latest['signal']

# Convert to scalar if they are Series
if isinstance(prev_signal, pd.Series):
    prev_signal = prev_signal.iloc[0]
if isinstance(latest_signal, pd.Series):
    latest_signal = latest_signal.iloc[0]

if 'last_signal' not in st.session_state:
    st.session_state.last_signal = 0

if prev_signal != latest_signal and latest_signal != st.session_state.last_signal:
    st.session_state.last_signal = latest_signal

    # ... your message and email sending code ...
