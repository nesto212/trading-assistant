import smtplib
from email.mime.text import MIMEText
import streamlit as st

# Load credentials from secrets
EMAIL_SENDER = st.secrets["email"]["sender"]
EMAIL_RECEIVER = st.secrets["email"]["receiver"]
EMAIL_PASSWORD = st.secrets["email"]["password"]

# Compose the email
msg = MIMEText("✅ This is a test email sent from your Streamlit app.")
msg["Subject"] = "Test Email from Trading Assistant"
msg["From"] = EMAIL_SENDER
msg["To"] = EMAIL_RECEIVER

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()
    st.success("📤 Test email sent successfully!")
except Exception as e:
    st.error(f"❌ Failed to send test email: {e}")
