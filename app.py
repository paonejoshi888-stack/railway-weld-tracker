import streamlit as st
import pandas as pd
import datetime
import gspread
import os
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Railway Weld Tracker", layout="centered")

# =========================================================
# 0. PASSWORD PROTECTION
# =========================================================
def check_password():
    """Returns `True` if the user enters the correct password."""
    
    # Check if we are testing locally without secrets set up yet
    if "APP_PASSWORD" not in st.secrets:
        st.warning("⚠️ No password found in secrets. Bypassing login for local testing.")
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Team Login")
        st.text_input("Enter the team password to access the database", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Team Login")
        st.text_input("Enter the team password to access the database", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect Password")
        return False
    return True

if not check_password():
    st.stop()  # Stop the app here if the password is wrong

# =========================================================
# THE REST OF YOUR APP (Only runs if password is correct)
# =========================================================
st.title("🚆 Railway Weld Record Manager")

MIN_DATE = datetime.date(1994, 1, 1)

def parse_date(date_str):
    if not date_str or pd.isna(date_str): return None
    date_str = str(date_str).strip()
    if not date_str: return None
    try:
        if "/" in date_str: return datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
        else: return datetime.date.fromisoformat(date_str)
    except ValueError: return None

@st.cache_resource
def init_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    if os.path.exists('credentials.json'):
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    else:
        # Convert secrets to a standard dictionary and properly format the private key
        secrets_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in secrets_dict:
            secrets_dict["private_key"] = secrets_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets_dict, scope)
        
    client = gspread.authorize(creds)
    return client.open("Railway Weld Database").worksheet("WeldDetails")

try:
    sheet = init_connection()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

def get_data_df():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Record", "✏️ Modify Record", "🗑️ Delete Record", "📊 View Database"])

with tab1:
    st.subheader("Add a New Weld Record")
    with st.form("add_form", clear_on_submit=True):
        add_id = st.text_input("AT weld ID *")
        col1, col2, col3 = st.columns(3)
        add_dw = col1.date_input("Date of Welding *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_du = col2.date_input("Date of USFD Testing *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_due = col3.date_input("Due Date of USFD *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        col4, col5 = st.columns(2)
        add_loc = col4.selectbox("Flaw Location", ["", "FLANGE", "HEAD", "WEB"])
        add_probe = col5.selectbox("Probe Used", ["", "70 DEG", "0 DEG"])
        col6, col7 = st.columns(2)
        add_int_blank = col6.checkbox("Leave Flaw Intensity blank", value=True)
        add_int = col7.number_input("Flaw Intensity (%)", min_value=0, max_value=100, value=0, disabled=add_int_blank)
        add_class = st.selectbox("USFD Classification *", ["", "OK", "DFWO", "DFWR"])
        submitted = st.form_submit_button("Add Record", type="primary")
        
        if submitted:
            if not all([add_id, add_dw, add_du, add_due, add_class]):
                st.error("Please fill all required fields (*)")
            else:
                df = get_data_df()
                if not df.empty and "AT weld ID" in df.columns and add_id.strip() in df["AT weld ID"].astype(str).values:
                    st.error(f"Error: Weld ID '{add_id.strip()}' already exists.")
                else:
                    intensity_val = "" if add_int_blank else int(add_int)
                    new_row = [add_id.strip(), add_dw.strftime("%d/%m/%Y"), add_du.strftime("%d/%m/%Y"), 
                               add_due.strftime("%d/%m/%Y"), add_loc, add_probe, intensity_val, add_class, "In service", ""]
                    sheet.append_row(new_row)
                    st.success(f"Record '{add_id.strip()}' added to Google Sheet as 'In service'!")

with tab2:
    st.subheader("Modify Existing Record")
    search_id = st.text_input("Enter AT weld ID to search:")
    if st.button("Fetch Record"):
        df = get_data_df()
        if not df.empty and search_id.strip() in df["AT weld ID"].astype(str).values:
            row_idx = df[df["AT weld ID"].astype(str) == search_id.strip()].index[0]
            st.session_state['edit_row_num'] = int(row_idx) + 2 
            st.session_state['edit_data'] = df.iloc[row_idx].to_dict()
            st.success(f"Record '{search_id}' found!")
        else:
            st.session_state.pop('edit_data', None)
            st.error("Record not found.")

    if 'edit_data' in st.session_state:
        d = st.session_state['edit_data']
        with st.form("update_form"):
            u_dw = st.date_input("Date of Welding *", value=parse_date(d.get("DATE OF WELDING")), min_value=MIN_DATE, format="DD/MM/YYYY")
            u_du = st.date_input("Date of USFD Testing *", value=parse_date(d.get("DATE OF USFD TESTING")), min_value=MIN_DATE, format="DD/MM/YYYY")
            u_due = st.date_input("Due Date of USFD *", value=parse_date(d.get("DUE Date of USFD")), min_value=MIN_DATE, format="DD/MM/YYYY")
            loc_options = ["", "FLANGE", "HEAD", "WEB"]
            u_loc = st.selectbox("Flaw Location", loc_options, index=loc_options.index(d.get("FLAW LOCATION")) if d.get("FLAW LOCATION") in loc_options else 0)
            probe_options = ["", "70 DEG", "0 DEG"]
            u_probe = st.selectbox("Probe Used", probe_options, index=probe_options.index(d.get("PROBE USED")) if d.get("PROBE USED") in probe_options else 0)
            val_int = d.get("FLAW INTENSITY")
            is_blank = (val_int == "" or pd.isna(val_int) or val_int is None)
            u_int_blank = st.checkbox("Leave Flaw Intensity blank", value=is_blank)
            u_int = st.number_input("Flaw Intensity (%)", min_value=0, max_value=100, value=int(val_int) if not is_blank else 0)
            class_options = ["", "OK", "DFWO", "DFWR"]
            u_class = st.selectbox("USFD Classification *", class_options, index=class_options.index(d.get("USFD CLASSIFICATION")) if d.get("USFD CLASSIFICATION") in class_options else 0)
            
            st.markdown("---")
            st.markdown("**Update Weld Status**")
            status_options = ["In service", "Failed"]
            current_status = d.get("STATUS") if d.get("STATUS") in status_options else "In service"
            col8, col9 = st.columns(2)
            u_status = col8.selectbox("Current Status *", status_options, index=status_options.index(current_status))
            u_dof = col9.date_input("Date of Failure (Only required if Failed)", value=parse_date(d.get("DATE OF FAILURE")), min_value=MIN_DATE, format="DD/MM/YYYY")

            update_submitted = st.form_submit_button("Update Record", type="primary")
            if update_submitted:
                if u_status == "Failed" and u_dof is None:
                    st.error("Please provide a Date of Failure since the weld status is now 'Failed'.")
                else:
                    intensity_val = "" if u_int_blank else int(u_int)
                    failure_date_val = u_dof.strftime("%d/%m/%Y") if (u_status == "Failed" and u_dof) else ""
                    updated_values = [str(d.get("AT weld ID")), u_dw.strftime("%d/%m/%Y"), u_du.strftime("%d/%m/%Y"), 
                                      u_due.strftime("%d/%m/%Y"), u_loc, u_probe, intensity_val, u_class, u_status, failure_date_val]
                    row_num = st.session_state['edit_row_num']
                    sheet.update(f"A{row_num}:J{row_num}", [updated_values])
                    st.success("Record updated successfully!")
                    st.session_state.pop('edit_data', None)

with tab3:
    st.subheader("Delete a Record")
    st.warning("⚠️ Warning: Deleting a record is permanent and cannot be undone.")
    del_search_id = st.text_input("Enter AT weld ID to delete:")
    if st.button("Delete Record", type="primary"):
        if not del_search_id.strip():
            st.error("Please enter an AT weld ID.")
        else:
            df = get_data_df()
            if not df.empty and del_search_id.strip() in df["AT weld ID"].astype(str).values:
                row_idx = df[df["AT weld ID"].astype(str) == del_search_id.strip()].index[0]
                sheet.delete_rows(int(row_idx) + 2)
                st.success(f"Record '{del_search_id.strip()}' was successfully deleted.")
                if 'edit_data' in st.session_state and st.session_state['edit_data'].get("AT weld ID") == del_search_id.strip():
                    st.session_state.pop('edit_data', None)
            else:
                st.error("Record not found in the database.")

with tab4:
    st.subheader("Live Google Sheet View")
    df = get_data_df()
    if df.empty:
        st.info("The database is currently empty. Add records using the 'Add Record' tab.")
    else:
        st.dataframe(df, use_container_width=True)
