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

def post_data(endpoint: str, data: dict = None):
    headers = {
        "X-Admin-Key": ADMIN_KEY,
        "Content-Type": "application/json"
    }
    try:
        response = requests.put(f"{API_BASE_URL}{endpoint}", json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Failed: {e}")
        if hasattr(e.response, "json"):
            st.error(e.response.json())
        return None

def post_data_post(endpoint: str, data: dict = None):
    headers = {
        "X-Admin-Key": ADMIN_KEY,
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Failed: {e}")
        if hasattr(e.response, "json"):
            st.error(e.response.json())
        return None

def delete_data(endpoint: str):
    headers = {
        "X-Admin-Key": ADMIN_KEY
    }
    try:
        response = requests.delete(f"{API_BASE_URL}{endpoint}", headers=headers)
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
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview Dashboard", "🏆 Top Consumers", "👥 User Management", "💳 Package Management"])

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

with tab4:
    st.header("Package Management")
    
    # Sub-tabs for different operations
    subtab1, subtab2, subtab3, subtab4 = st.tabs(["📋 List Packages", "➕ Create Package", "✏️ Edit Package", "👤 Assign to User"])
    
    # Fetch all packages (including inactive)
    @st.cache_data(ttl=30)
    def fetch_all_packages():
        headers = {"X-Admin-Key": ADMIN_KEY}
        try:
            response = requests.get(f"{API_BASE_URL}/admin/packages", headers=headers)
            response.raise_for_status()
            return response.json()
        except:
            return []
    
    packages = fetch_all_packages()
    
    with subtab1:
        st.subheader("All Packages")
        if packages:
            df_packages = pd.DataFrame(packages)
            # Add status indicator
            df_packages['status'] = df_packages['is_active'].apply(lambda x: "✅ Active" if x else "❌ Inactive")
            st.dataframe(df_packages[['name', 'price', 'billing_period', 'daily_upload_limit', 'daily_nutrition_limit', 'status']], use_container_width=True)
            
            st.subheader("Activate/Deactivate Package")
            package_options = {pkg['id']: f"{pkg['name']} ({'Active' if pkg['is_active'] else 'Inactive'})" for pkg in packages}
            selected_pkg_id = st.selectbox("Select Package", options=list(package_options.keys()), format_func=lambda x: package_options[x], key="activate_pkg")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Activate Package", key="activate_btn"):
                    result = post_data_post(f"/admin/packages/{selected_pkg_id}/activate", {})
                    if result:
                        st.success(f"Package activated!")
                        st.cache_data.clear()
                        st.rerun()
            with col2:
                if st.button("Deactivate Package", key="deactivate_btn"):
                    result = delete_data(f"/admin/packages/{selected_pkg_id}")
                    if result:
                        st.success(f"Package deactivated!")
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.info("No packages found.")
    
    with subtab2:
        st.subheader("Create New Package")
        
        with st.form("create_package_form"):
            name = st.text_input("Package Name")
            price = st.number_input("Price ($)", min_value=0.0, value=0.0, step=1.0)
            billing_period = st.selectbox("Billing Period", ["free", "monthly", "yearly"])
            daily_upload_limit = st.number_input("Daily Upload Limit", min_value=1, value=20)
            daily_nutrition_limit = st.number_input("Daily Nutrition Analysis Limit", min_value=1, value=20)
            
            st.subheader("Features")
            food_analysis = st.checkbox("Food Analysis", value=True)
            nutrition_advice = st.checkbox("Nutrition Advice", value=True)
            priority_support = st.checkbox("Priority Support", value=False)
            advanced_analytics = st.checkbox("Advanced Analytics", value=False)
            annual_discount = st.checkbox("Annual Discount", value=False)
            
            features = {
                "food_analysis": food_analysis,
                "nutrition_advice": nutrition_advice,
                "priority_support": priority_support,
                "advanced_analytics": advanced_analytics,
                "annual_discount": annual_discount
            }
            
            is_active = st.checkbox("Active", value=True)
            
            submit = st.form_submit_button("Create Package")
            
            if submit:
                data = {
                    "name": name,
                    "price": price,
                    "billing_period": billing_period,
                    "daily_upload_limit": daily_upload_limit,
                    "daily_nutrition_limit": daily_nutrition_limit,
                    "features": features,
                    "is_active": is_active
                }
                result = post_data_post("/admin/packages", data)
                if result:
                    st.success(f"Package '{name}' created successfully!")
                    st.cache_data.clear()
    
    with subtab3:
        st.subheader("Edit Package")
        
        if packages:
            # Select package to edit
            edit_package_options = {pkg['id']: f"{pkg['name']} - ${pkg['price']}/{pkg['billing_period']}" for pkg in packages}
            edit_selected_id = st.selectbox("Select Package to Edit", options=list(edit_package_options.keys()), format_func=lambda x: edit_package_options[x], key="edit_pkg_select")
            
            # Get selected package details
            selected_pkg = next((p for p in packages if p['id'] == edit_selected_id), None)
            
            if selected_pkg:
                with st.form("edit_package_form"):
                    edit_name = st.text_input("Package Name", value=selected_pkg['name'])
                    edit_price = st.number_input("Price ($)", min_value=0.0, value=float(selected_pkg['price']), step=1.0)
                    edit_billing_period = st.selectbox("Billing Period", ["free", "monthly", "yearly"], index=["free", "monthly", "yearly"].index(selected_pkg['billing_period']))
                    edit_daily_upload = st.number_input("Daily Upload Limit", min_value=1, value=selected_pkg['daily_upload_limit'])
                    edit_daily_nutrition = st.number_input("Daily Nutrition Analysis Limit", min_value=1, value=selected_pkg['daily_nutrition_limit'])
                    
                    st.subheader("Features")
                    feat = selected_pkg.get('features', {})
                    edit_food_analysis = st.checkbox("Food Analysis", value=feat.get('food_analysis', True))
                    edit_nutrition_advice = st.checkbox("Nutrition Advice", value=feat.get('nutrition_advice', True))
                    edit_priority_support = st.checkbox("Priority Support", value=feat.get('priority_support', False))
                    edit_advanced_analytics = st.checkbox("Advanced Analytics", value=feat.get('advanced_analytics', False))
                    edit_annual_discount = st.checkbox("Annual Discount", value=feat.get('annual_discount', False))
                    
                    edit_features = {
                        "food_analysis": edit_food_analysis,
                        "nutrition_advice": edit_nutrition_advice,
                        "priority_support": edit_priority_support,
                        "advanced_analytics": edit_advanced_analytics,
                        "annual_discount": edit_annual_discount
                    }
                    
                    edit_active = st.checkbox("Active", value=selected_pkg['is_active'])
                    
                    edit_submit = st.form_submit_button("Update Package")
                    
                    if edit_submit:
                        data = {
                            "name": edit_name,
                            "price": edit_price,
                            "billing_period": edit_billing_period,
                            "daily_upload_limit": edit_daily_upload,
                            "daily_nutrition_limit": edit_daily_nutrition_limit,
                            "features": edit_features,
                            "is_active": edit_active
                        }
                        result = post_data(f"/admin/packages/{edit_selected_id}", data)
                        if result:
                            st.success(f"Package '{edit_name}' updated successfully!")
                            st.cache_data.clear()
        else:
            st.info("No packages found.")
    
    with subtab4:
        st.subheader("Assign Package to User")
        
        # Get only active packages
        active_packages = [p for p in packages if p['is_active']] if packages else []
        
        if active_packages and users:
            df_users = pd.DataFrame(users)
            
            # Select user
            selected_email = st.selectbox("Select User", df_users['email'].tolist(), key="package_user_select")
            user_id = df_users[df_users['email'] == selected_email]['id'].iloc[0]
            
            # Show current subscription
            current_sub = fetch_data(f"/admin/users/{user_id}/subscription")
            
            if current_sub and current_sub.get('package'):
                st.info(f"Current Package: **{current_sub['package']['name']}** (${current_sub['package']['price']}/{current_sub['package']['billing_period']})")
                if current_sub.get('subscription', {}).get('end_date'):
                    st.info(f"Subscription ends: {current_sub['subscription']['end_date']}")
            else:
                st.info("User has no active subscription")
            
            # Select new package
            package_options = {pkg['id']: f"{pkg['name']} - ${pkg['price']}/{pkg['billing_period']}" for pkg in active_packages}
            selected_package_id = st.selectbox("Select New Package", options=list(package_options.keys()), format_func=lambda x: package_options[x])
            
            # Optional: custom duration
            use_custom_duration = st.checkbox("Set custom duration (days)")
            custom_duration = None
            if use_custom_duration:
                custom_duration = st.number_input("Duration (days)", min_value=1, max_value=365, value=30)
            
            if st.button("Update User Package"):
                data = {
                    "package_id": selected_package_id,
                    "duration_days": custom_duration
                }
                result = post_data(f"/admin/users/{user_id}/package", data)
                if result:
                    st.success(f"Successfully updated user package to **{result['package']['name']}**")
                    st.cache_data.clear()
        else:
            if not active_packages:
                st.warning("No active packages available. Please create a package first.")
            if not users:
                st.warning("No users available.")
