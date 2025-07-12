import streamlit as st
import sqlite3
import bcrypt
from datetime import datetime

# --- Database setup ---
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (username TEXT PRIMARY KEY, email TEXT, password_hash BLOB, paid INTEGER, last_login TEXT)''')
conn.commit()

# --- Helper functions ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, pw_hash):
    return bcrypt.checkpw(password.encode(), pw_hash)

def register_user(username, email, password):
    pw_hash = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  (username, email, pw_hash, 0, ""))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    c.execute("SELECT password_hash, paid FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result:
        pw_hash, paid = result
        if verify_password(password, pw_hash):
            return paid == 1
    return False

def update_last_login(username):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE users SET last_login = ? WHERE username = ?", (now, username))
    conn.commit()

def mark_user_paid(username):
    c.execute("UPDATE users SET paid = 1 WHERE username = ?", (username,))
    conn.commit()

# --- Streamlit app ---
st.title("🔒 Secure Trading App")

menu = ["Home", "Register", "Login"]
choice = st.sidebar.selectbox("Menu", menu)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if choice == "Register":
    st.subheader("Create a new account")
    new_user = st.text_input("Username")
    new_email = st.text_input("Email")
    new_password = st.text_input("Password", type="password")
    if st.button("Register"):
        if register_user(new_user, new_email, new_password):
            st.success("User registered! Please proceed to login.")
        else:
            st.error("Username already exists.")

elif choice == "Login":
    st.subheader("Login to your account")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login_user(username, password):
            update_last_login(username)
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid username/password or payment required.")

elif choice == "Home":
    if st.session_state.logged_in:
        st.success(f"Logged in as {st.session_state.username}")
        st.write("This is your secure trading app content.")
        # Here you can show the main app logic and data
    else:
        st.warning("Please login or register to access the app.")
