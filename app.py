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
# 1. DATABASE CONNECTION
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
    wb = client.open("Railway Weld Database")
    return wb.worksheet("WeldDetails"), wb.worksheet("USFDDetails")

try:
    weld_sheet, usfd_sheet = init_connection()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

def get_weld_df():
    return pd.DataFrame(weld_sheet.get_all_records())

def get_usfd_df():
    return pd.DataFrame(usfd_sheet.get_all_records())

# =========================================================
# TABS SETUP
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "➕ Add Weld (MMG)", 
    "🩺 USFD Testing", 
    "✏️ Modify Weld", 
    "🗑️ Delete", 
    "📊 View Database"
])

# ---------------------------------------------------------
# TAB 1: ADD WELD (MMG) -> Goes to WeldDetails
# ---------------------------------------------------------
with tab1:
    st.subheader("Add a New Weld Record (MMG Team)")
    with st.form("add_weld_form", clear_on_submit=True):
        st.markdown("**1. Build AT Weld ID**")
        col_at, col_km, col_tp, col_side, col_let = st.columns([0.4, 1.5, 1.5, 2.8, 2.3])
        col_at.markdown("<h4 style='text-align: center; margin-top: 35px;'>AT</h4>", unsafe_allow_html=True)
        
        id_km = col_km.text_input("3 Digits * - KM", max_chars=3, placeholder="001")
        id_tp = col_tp.text_input("2 Digits * - TP no.", max_chars=2, placeholder="10")
        id_side = col_side.text_input("2 Digits * - RHS even, LHS odd", max_chars=2, placeholder="77")
        id_let = col_let.text_input("Letter(s) - If replacement", placeholder="A")
        
        st.markdown("---")
        st.markdown("**2. Technical Details**")
        
        c1, c2, c3 = st.columns(3)
        add_dw = c1.date_input("Date of Welding *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_loc = c2.text_input("Location *", placeholder="e.g. Km 75/0-5")
        add_rt = c3.number_input("Reaction Time (secs) *", min_value=0, max_value=60, value=0)
        
        c4, c5, c6 = st.columns(3)
        add_ml = c4.selectbox("Main/Loop *", ["", "Main", "Loop"])
        add_lhrh = c5.selectbox("LH/RH *", ["", "LH", "RH"])
        add_sec = c6.text_input("Section *")
        
        c7, c8, c9 = st.columns(3)
        add_rm = c7.text_input("Rolling Mark *")
        add_ag = c8.text_input("Agency Code *")
        add_welder = c9.number_input("Welder Code *", min_value=0, step=1, value=0)
        
        add_dpm = st.date_input("Date of Portion Manufacture *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        
        submitted_weld = st.form_submit_button("Save Weld Record", type="primary")
        
        if submitted_weld:
            if not id_km.strip() or not id_tp.strip() or not id_side.strip():
                st.error("Please fill all required Weld ID fields (digits).")
            elif not all([add_dw, add_loc, add_ml, add_lhrh, add_sec, add_rm, add_ag, add_dpm]):
                st.error("Please fill all required fields (*).")
            else:
                assembled_id = f"AT{id_km.strip().zfill(3)}-{id_tp.strip().zfill(2)}-{id_side.strip().zfill(2)}{id_let.strip().upper()}"
                
                if not re.match(r"^AT\d{3}-\d{2}-\d{2}[A-Z]*$", assembled_id):
                    st.error("⚠️ Invalid ID Format!")
                else:
                    df = get_weld_df()
                    if not df.empty and "AT weld ID" in df.columns and assembled_id in df["AT weld ID"].astype(str).values:
                        st.error(f"Error: Weld ID '{assembled_id}' already exists in Weld Database.")
                    else:
                        new_row = [
                            assembled_id, add_dw.strftime("%d/%m/%Y"), add_loc.strip(), 
                            int(add_rt), add_ml, add_lhrh, add_sec.strip(), 
                            add_rm.strip(), add_ag.strip(), add_dpm.strftime("%d/%m/%Y"), int(add_welder)
                        ]
                        weld_sheet.append_row(new_row)
                        st.success(f"✅ Record '{assembled_id}' successfully added to Weld Database!")

# ---------------------------------------------------------
# TAB 2: USFD TESTING (Multi-History) -> Goes to USFDDetails
# ---------------------------------------------------------
with tab2:
    st.subheader("USFD Testing Data & History")
    usfd_search_id = st.text_input("Enter AT weld ID to view or log tests (e.g. AT001-10-77):")
    
    if st.button("Fetch USFD Records"):
        st.session_state['usfd_active_search'] = usfd_search_id.strip().upper()
        
    if 'usfd_active_search' in st.session_state and st.session_state['usfd_active_search']:
        search_clean = st.session_state['usfd_active_search']
        weld_df = get_weld_df()
        
        if weld_df.empty or search_clean not in weld_df["AT weld ID"].astype(str).values:
            st.error(f"⚠️ Weld ID '{search_clean}' not found in the MMG Weld Database. Please add it there first.")
        else:
            usfd_df = get_usfd_df()
            history_df = pd.DataFrame()
            if not usfd_df.empty and "AT weld ID" in usfd_df.columns:
                history_df = usfd_df[usfd_df["AT weld ID"].astype(str) == search_clean]
            
            # 1. Show the historical data table
            if not history_df.empty:
                st.markdown(f"### 📜 Test History for {search_clean}")
                st.dataframe(history_df, use_container_width=True)
            else:
                st.info(f"No previous USFD tests found for {search_clean}. The next entry will be its first test.")
            
            st.markdown("---")
            action = st.radio("What would you like to do?", ["Log a New Test", "Edit a Past Test"], horizontal=True)
            
            # 2A. Log a brand new test (Appends a row)
            if action == "Log a New Test":
                with st.form("usfd_add_form"):
                    c1, c2 = st.columns(2)
                    ua_du = c1.date_input("Date of USFD Testing *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
                    ua_due = c2.date_input("Due Date of USFD Testing *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
                    
                    ua_loc = st.text_input("Location *", placeholder="e.g. Km 75/0-5")
                    
                    c3, c4 = st.columns(2)
                    ua_flaw = c3.selectbox("Flaw Location", ["", "Flange", "Web", "Head"])
                    ua_probe = c4.selectbox("Probe Used", ["", "70deg", "45deg", "0deg"])
                    
                    c5, c6 = st.columns(2)
                    ua_int = c5.number_input("Flaw Intensity (0-100%)", min_value=0, max_value=100, value=0)
                    ua_class = c6.selectbox("Classification *", ["", "OK", "DFWO", "DFWR"])
                    
                    if st.form_submit_button("Save New Test", type="primary"):
                        if not all([ua_du, ua_due, ua_loc.strip(), ua_class]):
                            st.error("Please fill all required fields (*)")
                        else:
                            row_data = [
                                search_clean, ua_du.strftime("%d/%m/%Y"), ua_due.strftime("%d/%m/%Y"), 
                                ua_loc.strip(), ua_flaw, ua_probe, int(ua_int), ua_class
                            ]
                            usfd_sheet.append_row(row_data)
                            st.success("✅ New test logged! Click 'Fetch USFD Records' to refresh history.")
            
            # 2B. Edit an old test (Updates specific row)
            elif action == "Edit a Past Test":
                if history_df.empty:
                    st.warning("No past tests available to edit.")
                else:
                    # Create a dropdown mapping the UI text to the real DataFrame Index
                    opts = {idx: f"Test Date: {row['Date of USFD testing']} | Class: {row.get('Classification','')}" for idx, row in history_df.iterrows()}
                    sel_idx = st.selectbox("Select Test to Correct:", options=list(opts.keys()), format_func=lambda x: opts[x])
                    d = history_df.loc[sel_idx].to_dict()
                    
                    with st.form("usfd_edit_form"):
                        c1, c2 = st.columns(2)
                        ue_du = c1.date_input("Date of USFD Testing *", value=parse_date(d.get("Date of USFD testing")), min_value=MIN_DATE, format="DD/MM/YYYY")
                        ue_due = c2.date_input("Due Date of USFD Testing *", value=parse_date(d.get("Due date of USFD testing")), min_value=MIN_DATE, format="DD/MM/YYYY")
                        
                        ue_loc = st.text_input("Location *", value=str(d.get("Location", "")))
                        
                        c3, c4 = st.columns(2)
                        flaw_opts = ["", "Flange", "Web", "Head"]
                        ue_flaw = c3.selectbox("Flaw Location", flaw_opts, index=flaw_opts.index(d.get("Flaw Location")) if d.get("Flaw Location") in flaw_opts else 0)
                        
                        probe_opts = ["", "70deg", "45deg", "0deg"]
                        ue_probe = c4.selectbox("Probe Used", probe_opts, index=probe_opts.index(d.get("Probe Used")) if d.get("Probe Used") in probe_opts else 0)
                        
                        c5, c6 = st.columns(2)
                        val_int = d.get("Flaw Intensity")
                        is_blank = (val_int == "" or pd.isna(val_int) or val_int is None)
                        ue_int = c5.number_input("Flaw Intensity (0-100%)", min_value=0, max_value=100, value=0 if is_blank else int(val_int))
                        
                        class_opts = ["", "OK", "DFWO", "DFWR"]
                        ue_class = c6.selectbox("Classification *", class_opts, index=class_opts.index(d.get("Classification")) if d.get("Classification") in class_opts else 0)
                        
                        if st.form_submit_button("Update Specific Test", type="primary"):
                            if not all([ue_du, ue_due, ue_loc.strip(), ue_class]):
                                st.error("Please fill all required fields (*)")
                            else:
                                row_data = [
                                    search_clean, ue_du.strftime("%d/%m/%Y"), ue_due.strftime("%d/%m/%Y"), 
                                    ue_loc.strip(), ue_flaw, ue_probe, int(ue_int), ue_class
                                ]
                                row_num = int(sel_idx) + 2
                                usfd_sheet.update(f"A{row_num}:H{row_num}", [row_data])
                                st.success("✅ Historical record updated! Click 'Fetch USFD Records' to refresh history.")

# ---------------------------------------------------------
# TAB 3: MODIFY WELD (MMG)
# ---------------------------------------------------------
with tab3:
    st.subheader("Modify Existing MMG Weld Record")
    mod_search_id = st.text_input("Enter AT weld ID to edit MMG details:")
    
    if st.button("Fetch MMG Record"):
        df = get_weld_df()
        search_clean = mod_search_id.strip().upper()
        if not df.empty and search_clean in df["AT weld ID"].astype(str).values:
            row_idx = df[df["AT weld ID"].astype(str) == search_clean].index[0]
            st.session_state['mod_weld_row'] = int(row_idx) + 2 
            st.session_state['mod_weld_data'] = df.iloc[row_idx].to_dict()
            st.success(f"Record '{search_clean}' found!")
        else:
            st.session_state.pop('mod_weld_data', None)
            st.error("Record not found in Weld Database.")

    if 'mod_weld_data' in st.session_state:
        d = st.session_state['mod_weld_data']
        with st.form("mod_weld_form"):
            c1, c2, c3 = st.columns(3)
            m_dw = c1.date_input("Date of Welding *", value=parse_date(d.get("Date of Welding")), min_value=MIN_DATE, format="DD/MM/YYYY")
            m_loc = c2.text_input("Location *", value=str(d.get("Location", "")))
            m_rt = c3.number_input("Reaction Time (secs) *", min_value=0, max_value=60, value=int(d.get("Reaction Time", 0) if str(d.get("Reaction Time", "")).isdigit() else 0))
            
            c4, c5, c6 = st.columns(3)
            ml_opts = ["", "Main", "Loop"]
            m_ml = c4.selectbox("Main/Loop *", ml_opts, index=ml_opts.index(d.get("Main/Loop")) if d.get("Main/Loop") in ml_opts else 0)
            
            lhrh_opts = ["", "LH", "RH"]
            m_lhrh = c5.selectbox("LH/RH *", lhrh_opts, index=lhrh_opts.index(d.get("LH/RH")) if d.get("LH/RH") in lhrh_opts else 0)
            m_sec = c6.text_input("Section *", value=str(d.get("Section", "")))
            
            c7, c8, c9 = st.columns(3)
            m_rm = c7.text_input("Rolling Mark *", value=str(d.get("Rolling Mark", "")))
            m_ag = c8.text_input("Agency Code *", value=str(d.get("Agency Code", "")))
            m_welder = c9.number_input("Welder Code *", min_value=0, step=1, value=int(d.get("Welder code", 0) if str(d.get("Welder code", "")).isdigit() else 0))
            
            m_dpm = st.date_input("Date of Portion Manufacture *", value=parse_date(d.get("Date of Portion Manufacture")), min_value=MIN_DATE, format="DD/MM/YYYY")
            
            if st.form_submit_button("Update MMG Record", type="primary"):
                updated_values = [
                    str(d.get("AT weld ID")), m_dw.strftime("%d/%m/%Y"), m_loc.strip(), 
                    int(m_rt), m_ml, m_lhrh, m_sec.strip(), m_rm.strip(), 
                    m_ag.strip(), m_dpm.strftime("%d/%m/%Y"), int(m_welder)
                ]
                row_num = st.session_state['mod_weld_row']
                weld_sheet.update(f"A{row_num}:K{row_num}", [updated_values])
                st.success("✅ MMG Record updated successfully!")
                st.session_state.pop('mod_weld_data', None)

# ---------------------------------------------------------
# TAB 4: DELETE RECORD (Cascading Delete)
# ---------------------------------------------------------
with tab4:
    st.subheader("Delete a Record Completely")
    st.warning("⚠️ Warning: This will permanently delete the ID from the MMG Database AND all its historical tests in the USFD Database.")
    del_search_id = st.text_input("Enter AT weld ID to delete:")
    
    if st.button("Delete Record", type="primary"):
        if not del_search_id.strip():
            st.error("Please enter an AT weld ID.")
        else:
            del_clean = del_search_id.strip().upper()
            weld_df = get_weld_df()
            usfd_df = get_usfd_df()
            deleted_something = False
            
            # Delete from USFD sheet first (Multiple rows possible)
            if not usfd_df.empty and "AT weld ID" in usfd_df.columns and del_clean in usfd_df["AT weld ID"].astype(str).values:
                usfd_indices = usfd_df[usfd_df["AT weld ID"].astype(str) == del_clean].index.tolist()
                # Crucial: Delete from bottom up so row indexes don't shift during deletion loop!
                for idx in sorted(usfd_indices, reverse=True):
                    usfd_sheet.delete_rows(int(idx) + 2)
                st.success(f"🗑️ Deleted {len(usfd_indices)} historical tests from USFD Database.")
                deleted_something = True
                
            # Delete from Master Weld sheet
            if not weld_df.empty and del_clean in weld_df["AT weld ID"].astype(str).values:
                row_idx = weld_df[weld_df["AT weld ID"].astype(str) == del_clean].index[0]
                weld_sheet.delete_rows(int(row_idx) + 2)
                st.success(f"🗑️ Deleted Master Record '{del_clean}' from Weld Database.")
                deleted_something = True
                
            if not deleted_something:
                st.error(f"Record '{del_clean}' not found in any database.")

# ---------------------------------------------------------
# TAB 5: VIEW DATABASES 
# ---------------------------------------------------------
with tab5:
    st.subheader("Live Google Sheet Views")
    
    st.markdown("### 1. MMG Weld Database")
    weld_df = get_weld_df()
    if weld_df.empty: st.info("Weld database is empty.")
    else: st.dataframe(weld_df, use_container_width=True)
    
    st.markdown("### 2. USFD Testing Database (Log)")
    usfd_df = get_usfd_df()
    if usfd_df.empty: st.info("USFD database is empty.")
    else: st.dataframe(usfd_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📥 Download Data")
    
    col_dl1, col_dl2 = st.columns(2)
    
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            weld_df.to_excel(writer, index=False, sheet_name='Weld_Details')
            usfd_df.to_excel(writer, index=False, sheet_name='USFD_History')
        
        col_dl1.download_button(
            label="📊 Download Combined Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"Weld_and_USFD_Records_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        col_dl1.info("⚠️ Ensure 'openpyxl' is in requirements.txt for Excel downloads.")

    col_dl2.download_button(
        label="📄 Download Weld Details (CSV)",
        data=weld_df.to_csv(index=False).encode('utf-8'),
        file_name=f"Weld_Details_{datetime.date.today()}.csv",
        mime="text/csv",
    )
    col_dl2.download_button(
        label="📄 Download USFD History (CSV)",
        data=usfd_df.to_csv(index=False).encode('utf-8'),
        file_name=f"USFD_History_{datetime.date.today()}.csv",
        mime="text/csv",
    )
