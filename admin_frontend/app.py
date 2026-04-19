import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# Page Configuration
st.set_page_config(
    page_title="DietGuard Admin Dashboard",
    page_icon="🛡️",
    layout="wide"
)

# Shared API request function
@st.cache_data(ttl=60)
def fetch_data(endpoint: str, params: dict = None):
    headers = {
        "X-Admin-Key": ADMIN_KEY
    }
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Failed: {e}")
        if hasattr(e.response, "json"):
            st.error(e.response.json())
        return None

# Sidebar Authentication check
if not ADMIN_KEY:
    st.sidebar.error("ADMIN_KEY not found in environment.")
    st.stop()

st.title("DietGuard Admin Dashboard")

# Create tabs
tab1, tab2, tab3 = st.tabs(["📊 Overview Dashboard", "🏆 Top Consumers", "👥 User Management"])

with tab1:
    st.header("Token Usage Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Daily Usage")
        days = st.slider("Days to look back", min_value=1, max_value=90, value=30)
        daily_stats = fetch_data("/admin/token-stats/daily", params={"days": days})
        
        if daily_stats:
            df_daily = pd.DataFrame(daily_stats)
            if not df_daily.empty:
                df_daily['date'] = pd.to_datetime(df_daily['date'])
                df_daily.set_index('date', inplace=True)
                
                st.line_chart(df_daily[['total_input_tokens', 'total_output_tokens']])
                st.metric("Total API Calls (Period)", f"{df_daily['api_calls'].sum():,}")
            else:
                st.info("No daily usage data found.")
                
    with col2:
        st.subheader("Model Usage")
        model_stats = fetch_data("/admin/token-stats/models")
        
        if model_stats:
            df_models = pd.DataFrame(model_stats)
            if not df_models.empty:
                st.bar_chart(df_models.set_index("model_name")[["total_tokens"]])
                st.dataframe(df_models, use_container_width=True)
            else:
                st.info("No model usage data found.")

with tab2:
    st.header("Top Token Consumers")
    limit = st.number_input("Number of users to fetch", min_value=1, max_value=100, value=10)
    top_consumers = fetch_data("/admin/token-stats/top-consumers", params={"limit": limit})
    
    if top_consumers:
        df_top = pd.DataFrame(top_consumers)
        if not df_top.empty:
            # Format numbers
            for col in ['total_input_tokens', 'total_output_tokens', 'total_tokens', 'api_calls']:
                if col in df_top.columns:
                    df_top[col] = df_top[col].apply(lambda x: f"{x:,}")
            st.dataframe(df_top, use_container_width=True)
        else:
            st.info("No token consumers found.")

with tab3:
    st.header("User Management")
    
    if st.button("Refresh Users"):
        st.cache_data.clear()
        
    users = fetch_data("/admin/users", params={"skip": 0, "limit": 100})
    
    if users:
        df_users = pd.DataFrame(users)
        if not df_users.empty:
            st.dataframe(df_users[['id', 'email', 'isActive', 'createdAt', 'roles']], use_container_width=True)
            
            st.subheader("Fetch User Token Stats")
            selected_email = st.selectbox("Select User", df_users['email'].tolist())
            user_id = df_users[df_users['email'] == selected_email]['id'].iloc[0]
            
            if st.button("Get Token Stats"):
                user_stats = fetch_data(f"/admin/users/{user_id}/token-stats")
                if user_stats:
                    st.json(user_stats)
        else:
            st.info("No users found.")
