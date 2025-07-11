import smtplib
from email.mime.text import MIMEText

msg = MIMEText("This is a test email from your Streamlit trading assistant.")
msg["Subject"] = "Test Email"
msg["From"] = st.secrets["email"]["sender"]
msg["To"] = st.secrets["email"]["receiver"]

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(st.secrets["email"]["sender"], st.secrets["email"]["password"])
server.send_message(msg)
server.quit()
