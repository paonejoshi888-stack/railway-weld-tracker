import streamlit as st
import pandas as pd
import datetime
import gspread
import os
import re
import io
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Railway Weld Tracker", layout="wide") 

# =========================================================
# 0. PASSWORD PROTECTION
# =========================================================
def check_password():
    if "APP_PASSWORD" not in st.secrets:
        st.warning("⚠️ No password found in secrets. Bypassing login for local testing.")
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
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
    st.stop()

# =========================================================
# THE REST OF YOUR APP
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

# ---------------------------------------------------------
# 2. ADD RECORD TAB
# ---------------------------------------------------------
with tab1:
    st.subheader("Add a New Weld Record")
    with st.form("add_form", clear_on_submit=True):
        
        st.markdown("**Build AT Weld ID**")
        col_at, col_km, col_tp, col_side, col_let = st.columns([0.4, 1.5, 1.5, 2.8, 2.3])
        col_at.markdown("<h4 style='text-align: center; margin-top: 35px;'>AT</h4>", unsafe_allow_html=True)
        
        id_km = col_km.text_input("3 Digits * - KM", max_chars=3, placeholder="001")
        id_tp = col_tp.text_input("2 Digits * - TP no.", max_chars=2, placeholder="10")
        id_side = col_side.text_input("2 Digits * - RHS even, LHS odd", max_chars=2, placeholder="77")
        id_let = col_let.text_input("Letter(s) - If failed add A", placeholder="A")
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        add_dw = col1.date_input("Date of Welding *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_du = col2.date_input("Date of USFD Testing *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_due = col3.date_input("Due Date of USFD *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        
        col4, col5 = st.columns(2)
        add_loc = col4.selectbox("Flaw Location", ["", "FLANGE", "HEAD", "WEB"])
        add_probe = col5.selectbox("Probe Used", ["", "70 DEG", "0 DEG"])
        
        add_int = st.number_input("Flaw Intensity (%)", min_value=0, max_value=100, value=0)
        add_class = st.selectbox("USFD Classification *", ["", "OK", "DFWO", "DFWR"])
        
        submitted = st.form_submit_button("Add Record", type="primary")
        
        if submitted:
            if not id_km.strip() or not id_tp.strip() or not id_side.strip():
                st.error("Please fill all required Weld ID fields (digits).")
            elif not all([add_dw, add_du, add_due, add_class]):
                st.error("Please fill all other required fields (*)")
            else:
                km_clean = id_km.strip().zfill(3)
                tp_clean = id_tp.strip().zfill(2)
                side_clean = id_side.strip().zfill(2)
                let_clean = id_let.strip().upper()
                
                assembled_id = f"AT{km_clean}-{tp_clean}-{side_clean}{let_clean}"
                
                if not re.match(r"^AT\d{3}-\d{2}-\d{2}[A-Z]*$", assembled_id):
                    st.error("⚠️ Invalid ID Format! Please ensure you only entered numbers in the Digit boxes and letters in the Letter box.")
                else:
                    df = get_data_df()
                    if not df.empty and "AT weld ID" in df.columns and assembled_id in df["AT weld ID"].astype(str).values:
                        st.error(f"Error: Weld ID '{assembled_id}' already exists.")
                    else:
                        new_row = [
                            assembled_id, 
                            add_dw.strftime("%d/%m/%Y"), 
                            add_du.strftime("%d/%m/%Y"), 
                            add_due.strftime("%d/%m/%Y"), 
                            add_loc, 
                            add_probe, 
                            int(add_int), 
                            add_class, 
                            "In service", 
                            ""
                        ]
                        sheet.append_row(new_row)
                        st.success(f"Record '{assembled_id}' added to Google Sheet as 'In service'!")

# ---------------------------------------------------------
# 3. MODIFY RECORD TAB
# ---------------------------------------------------------
with tab2:
    st.subheader("Modify Existing Record")
    search_id = st.text_input("Enter AT weld ID to search (e.g. AT001-10-77 or AT001-10-77A):")
    if st.button("Fetch Record"):
        df = get_data_df()
        search_clean = search_id.strip().upper()
        if not df.empty and search_clean in df["AT weld ID"].astype(str).values:
            row_idx = df[df["AT weld ID"].astype(str) == search_clean].index[0]
            st.session_state['edit_row_num'] = int(row_idx) + 2 
            st.session_state['edit_data'] = df.iloc[row_idx].to_dict()
            st.success(f"Record '{search_clean}' found!")
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
            u_int = st.number_input("Flaw Intensity (%)", min_value=0, max_value=100, value=0 if is_blank else int(val_int))
            
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
                    failure_date_val = u_dof.strftime("%d/%m/%Y") if (u_status == "Failed" and u_dof) else ""
                    updated_values = [str(d.get("AT weld ID")).upper(), u_dw.strftime("%d/%m/%Y"), u_du.strftime("%d/%m/%Y"), 
                                      u_due.strftime("%d/%m/%Y"), u_loc, u_probe, int(u_int), u_class, u_status, failure_date_val]
                    row_num = st.session_state['edit_row_num']
                    sheet.update(f"A{row_num}:J{row_num}", [updated_values])
                    st.success("Record updated successfully!")
                    st.session_state.pop('edit_data', None)

# ---------------------------------------------------------
# 4. DELETE RECORD TAB
# ---------------------------------------------------------
with tab3:
    st.subheader("Delete a Record")
    st.warning("⚠️ Warning: Deleting a record is permanent and cannot be undone.")
    del_search_id = st.text_input("Enter AT weld ID to delete (e.g. AT001-10-77 or AT001-10-77A):")
    if st.button("Delete Record", type="primary"):
        if not del_search_id.strip():
            st.error("Please enter an AT weld ID.")
        else:
            df = get_data_df()
            del_clean = del_search_id.strip().upper()
            if not df.empty and del_clean in df["AT weld ID"].astype(str).values:
                row_idx = df[df["AT weld ID"].astype(str) == del_clean].index[0]
                sheet.delete_rows(int(row_idx) + 2)
                st.success(f"Record '{del_clean}' was successfully deleted.")
                if 'edit_data' in st.session_state and str(st.session_state['edit_data'].get("AT weld ID")).upper() == del_clean:
                    st.session_state.pop('edit_data', None)
            else:
                st.error("Record not found in the database.")

# ---------------------------------------------------------
# 5. VIEW DATABASE TAB
# ---------------------------------------------------------
with tab4:
    st.subheader("Live Google Sheet View")
    df = get_data_df()
    
    if df.empty:
        st.info("The database is currently empty. Add records using the 'Add Record' tab.")
    else:
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📥 Download Data")
        col_dl1, col_dl2 = st.columns(2)
        
        # 1. CSV Download Option (Foolproof, opens directly in Excel)
        csv_data = df.to_csv(index=False).encode('utf-8')
        col_dl1.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"Weld_Records_{datetime.date.today()}.csv",
            mime="text/csv",
        )
        
        # 2. Native Excel Download Option (Requires openpyxl)
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Weld_Records')
            
            col_dl2.download_button(
                label="📊 Download as Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Weld_Records_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            col_dl2.info("⚠️ Add 'openpyxl' to your requirements.txt in GitHub to enable the .xlsx download button.")
