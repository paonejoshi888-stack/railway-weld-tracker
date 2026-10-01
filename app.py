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
# 0. MULTI-USER LOGIN SYSTEM
# =========================================================
def check_password():
    if "user" in st.session_state:
        return True

    st.title("🔒 Divisional Login Portal")
    st.markdown("Please log in with your assigned Jurisdiction Username.")
    
    with st.form("login_form"):
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password").strip()
        submitted = st.form_submit_button("Login")
        
        if submitted:
            users = {
                "DEN_CHI": "pass123", "SSE_MNI": "pass123", "SSE_CHI": "pass123",
                "JE_KOL": "pass123", "JE_VEER": "pass123", "JE_KFD": "pass123", 
                "JE_KHED": "pass123", "JE_CHI": "pass123", "JE_SGR": "pass123",
                "SSE_SEC_RN": "pass123", "SSE_P_RN": "pass123", "AEN_RN": "pass123",
                "JE_ADVI": "pass123", "JE_VBW": "pass123", "SSE_VID": "pass123",
                "JE_KKW": "pass123", "JE_SWV": "pass123", "SSE_KKW": "pass123",
                "DEN_KKW": "pass123", "USFD_TEAM": "usfd123", "ADMIN": "admin123"
            }
            
            if "users" in st.secrets:
                users = dict(st.secrets["users"])
                
            if username in users and users[username] == password:
                st.session_state["user"] = username
                st.rerun()
            else:
                st.error("❌ Incorrect Username or Password")
    return False

if not check_password():
    st.stop()

st.sidebar.success(f"Logged in as: **{st.session_state['user']}**")
if st.sidebar.button("Log Out"):
    del st.session_state["user"]
    st.rerun()

# =========================================================
# 1. DATABASE CONNECTION & HELPER LOGIC
# =========================================================
st.title("🚆 Railway Weld Record Manager")
MIN_DATE = datetime.date(1994, 1, 1)

# Global Jurisdiction Mapping
JE_OPTIONS = {
    "All Division (Complete)": (-1, 9999),
    "DEN/CHI (Km 0-154)": (0, 154),
    "SSE/MNI (Km 0-79)": (0, 79),
    "SSE/CHI (Km 80-154)": (80, 154),
    "JE/KOL (Km 0-23)": (0, 23),
    "JE/VEER (Km 24-46)": (24, 46),
    "JE/KFD (Km 47-79)": (47, 79),
    "JE/KHED (Km 80-119)": (80, 119),
    "JE/CHI (Km 120-154)": (120, 154),
    "DEN/KKW (Km 226-378)": (226, 378),
    "SSE/Sec/RN (Km 191-226)": (191, 226),
    "SSE/P/RN (Km 154-226)": (154, 226),
    "AEN/RN (Km 154-226)": (154, 226),
    "SSE/VID (Km 226-299)": (226, 299),
    "SSE/KKW (Km 299-371)": (299, 371),
    "JE/SGR (Km 154-191)": (154, 191),
    "JE/ADVI (Km 226-258)": (226, 258),
    "JE/VBW (Km 258-299)": (258, 299),
    "JE/KKW (Km 299-337)": (299, 337),
    "JE/SWV (Km 337-371)": (337, 371),
    "Unassigned / Invalid KM": (-1, -1)
}

def parse_date(date_str):
    if not date_str or pd.isna(date_str): return None
    date_str = str(date_str).strip()
    if not date_str: return None
    try:
        if "/" in date_str: return datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
        else: return datetime.date.fromisoformat(date_str)
    except ValueError: return None

def extract_km(loc_str):
    if not loc_str or pd.isna(loc_str): return -1
    match = re.search(r'(\d+)', str(loc_str))
    return int(match.group(1)) if match else -1

def safe_int(val):
    try: return int(float(val))
    except: return 0

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
    "📊 View & Reports"
])

# ---------------------------------------------------------
# TAB 1: ADD WELD (MMG)
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
        st.markdown("**2. Physical & Location Details**")
        c1, c2, c3, c4 = st.columns(4)
        add_dw = c1.date_input("Date of Welding *", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")
        add_loc = c2.text_input("Location *", placeholder="e.g. Km 75/0-5")
        add_ml = c3.selectbox("Main/Loop *", ["", "Main", "Loop"])
        add_lhrh = c4.selectbox("LH/RH *", ["", "LH", "RH"])
        
        c5, c6, c7 = st.columns(3)
        add_sec = c5.text_input("Section *")
        add_rail = c6.selectbox("Rail Details *", ["", "52KG", "60KG"])
        add_rm = c7.text_input("Rolling Mark *")

        st.markdown("**3. Materials & Agency**")
        c8, c9, c10, c11, c11b = st.columns([1.5, 2, 1, 1, 1])
        
        ag_opts = ["", "ITC", "CKD", "OBOROI", "TPP", "SAGAR", "OTHER"]
        add_ag_sel = c8.selectbox("Agency Code *", ag_opts)
        add_ag_oth = c8.text_input("Specify Agency", key="add_ag_oth") if add_ag_sel == "OTHER" else ""
        add_ag = add_ag_oth if add_ag_sel == "OTHER" else add_ag_sel
        
        sup_opts = ["", "JE/MMG/CHI", "JE/MMG/RN", "JE/MMG/RAJP", "JE/MMG/KUDL", "Other"]
        add_sup_sel = c9.selectbox("Supervisor Code *", sup_opts)
        add_sup_oth = c9.text_input("Specify Supervisor", key="add_sup_oth") if add_sup_sel == "Other" else ""
        add_sup = add_sup_oth if add_sup_sel == "Other" else add_sup_sel
        
        add_welder = c10.number_input("Welder Code *", min_value=0, step=1, value=0)
        
        add_weldno_pfx = c11.selectbox("Weld Pfx *", ["LH", "RN"])
        add_weldno_num = c11b.number_input("Weld No. (INT) *", min_value=0, step=1, value=0)
        add_weldno = f"{add_weldno_pfx}{add_weldno_num}"
        
        c12, c13, c14 = st.columns(3)
        add_port = c12.text_input("Portion No.")
        add_batch = c13.text_input("Batch No.")
        add_dpm = c14.date_input("Date of Portion Mfg", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")

        st.markdown("**4. Execution Timings (Integer Only)**")
        c15, c16, c17, c18 = st.columns(4)
        add_rt = c15.number_input("Reaction Time (sec)", min_value=0, step=1, value=0)
        add_bf = c16.number_input("Block Time From (HHMM)", min_value=0, max_value=2359, step=1, value=0)
        add_bt = c17.number_input("Block Time To (HHMM)", min_value=0, max_value=2359, step=1, value=0)
        add_fg = c18.number_input("Finishing/Grinding Time (HHMM)", min_value=0, max_value=2359, step=1, value=0)
        
        c19, c20, c21 = st.columns(3)
        add_mw = c19.number_input("Mould Waiting Time (min)", min_value=0, step=1, value=0)
        add_ph = c20.number_input("Pre-heating Time (min)", min_value=0, step=1, value=0)
        add_tp = c21.number_input("Time 1st Train Passed (HHMM)", min_value=0, max_value=2359, step=1, value=0)

        st.markdown("**5. Dimensional Tolerances (Integer mm)**")
        c22, c23, c24, c25 = st.columns(4)
        add_1mt = c22.number_input("1m Top (mm)", step=1, value=0)
        add_1ms = c23.number_input("1m Side (mm)", step=1, value=0)
        add_10cv = c24.number_input("10cm Vert (mm)", step=1, value=0)
        add_10cl = c25.number_input("10cm Lat (mm)", step=1, value=0)

        submitted_weld = st.form_submit_button("Save Weld Record & Generate RDSO", type="primary")
        
        if submitted_weld:
            if not id_km.strip() or not id_tp.strip() or not id_side.strip():
                st.error("Please fill all required Weld ID fields (digits).")
            elif not all([add_dw, add_loc, add_ml, add_lhrh, add_sec, add_rail, add_ag, add_sup]):
                st.error("Please fill all required string dropdowns & locations (*).")
            else:
                assembled_id = f"AT{id_km.strip().zfill(3)}-{id_tp.strip().zfill(2)}-{id_side.strip().zfill(2)}{id_let.strip().upper()}"
                
                if not re.match(r"^AT\d{3}-\d{2}-\d{2}[A-Z]*$", assembled_id):
                    st.error("⚠️ Invalid ID Format!")
                else:
                    df = get_weld_df()
                    if not df.empty and "AT weld ID" in df.columns and assembled_id in df["AT weld ID"].astype(str).values:
                        st.error(f"Error: Weld ID '{assembled_id}' already exists in Weld Database.")
                    else:
                        month = add_dw.strftime("%m")
                        year_yy = add_dw.strftime("%y")
                        rdso_mark = f"{month}-{year_yy}-{add_ag.strip().upper()}-{add_welder}-{add_weldno}"
                        
                        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        dpm_str = add_dpm.strftime("%d/%m/%Y") if add_dpm else ""
                        
                        new_row = [
                            assembled_id, add_dw.strftime("%d/%m/%Y"), add_loc.strip(), add_ml, add_lhrh, 
                            add_sec.strip(), add_rail.strip(), add_port.strip(), add_batch.strip(), 
                            add_rm.strip(), add_ag.strip().upper(), add_sup.strip(), int(add_welder), 
                            add_weldno, dpm_str, int(add_rt), int(add_bf), int(add_bt), 
                            int(add_fg), int(add_mw), int(add_ph), int(add_1mt), int(add_1ms), 
                            int(add_10cv), int(add_10cl), int(add_tp), rdso_mark, 
                            st.session_state["user"], timestamp
                        ]
                        weld_sheet.append_row(new_row)
                        st.success(f"✅ Record '{assembled_id}' added! Auto-Generated RDSO Marking: **{rdso_mark}**")

# ---------------------------------------------------------
# TAB 2: USFD TESTING & AUDIT TRAIL
# ---------------------------------------------------------
with tab2:
    st.subheader("USFD Testing Data & Audit History")
    
    st.markdown("### 🔍 Search & Select Weld")
    df_weld = get_weld_df()
    
    if df_weld.empty:
        st.info("No welds currently exist in the MMG database.")
    else:
        # Convert welding dates to actual Date objects for range filtering
        df_weld["ParsedDate"] = pd.to_datetime(df_weld["Date of Welding"], format="%d/%m/%Y", errors='coerce').dt.date
        df_weld["KM_Value"] = df_weld["Location"].apply(extract_km)
        
        c_s1, c_s2, c_s3 = st.columns(3)
        start_d = c_s1.date_input("From Welding Date", value=datetime.date.today() - datetime.timedelta(days=30))
        end_d = c_s2.date_input("To Welding Date", value=datetime.date.today())
        sel_jur = c_s3.selectbox("Filter by Jurisdiction", list(JE_OPTIONS.keys()))
        
        min_k, max_k = JE_OPTIONS[sel_jur]
        
        mask_date = (df_weld["ParsedDate"] >= start_d) & (df_weld["ParsedDate"] <= end_d)
        
        if sel_jur == "All Division (Complete)":
            mask_jur = True
        elif sel_jur == "Unassigned / Invalid KM":
            mask_jur = (df_weld["KM_Value"] == -1)
        else:
            mask_jur = (df_weld["KM_Value"] >= min_k) & (df_weld["KM_Value"] <= max_k)
            
        filtered_weld_df = df_weld[mask_date & mask_jur]
        
        st.markdown("---")
        if filtered_weld_df.empty:
            st.warning("No welds found matching this Date Range and Jurisdiction.")
            st.session_state.pop('usfd_active_search', None)
        else:
            weld_list = sorted(filtered_weld_df["AT weld ID"].tolist())
            selected_weld_id = st.selectbox("Select Weld ID from Filtered List:", ["-- Select a Weld --"] + weld_list)
            
            if selected_weld_id != "-- Select a Weld --":
                st.session_state['usfd_active_search'] = selected_weld_id
            
            st.markdown("*Or manually override and type AT weld ID (e.g. AT001-10-77):*")
            usfd_search_id = st.text_input("Manual AT Weld ID Search:", key="manual_usfd")
            if st.button("Fetch Manual ID"):
                if usfd_search_id.strip():
                    st.session_state['usfd_active_search'] = usfd_search_id.strip().upper()

    # If an ID is active, show the history and actions
    if 'usfd_active_search' in st.session_state and st.session_state['usfd_active_search']:
        search_clean = st.session_state['usfd_active_search']
        
        if df_weld.empty or search_clean not in df_weld["AT weld ID"].astype(str).values:
            st.error(f"⚠️ Weld ID '{search_clean}' not found in the MMG Weld Database.")
        else:
            st.markdown(f"## 🎯 Active Weld: **{search_clean}**")
            usfd_df = get_usfd_df()
            history_df = pd.DataFrame()
            if not usfd_df.empty and "AT weld ID" in usfd_df.columns:
                history_df = usfd_df[usfd_df["AT weld ID"].astype(str) == search_clean]
            
            if not history_df.empty:
                st.markdown(f"### 📜 Test History")
                st.dataframe(history_df, use_container_width=True)
            else:
                st.info(f"No previous USFD tests found. The next entry will be its first test.")
            
            st.markdown("---")
            action = st.radio("What would you like to do?", ["Log a New Test", "Edit a Past Test", "Delete a Past Test"], horizontal=True)
            
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
                    ua_int = c5.number_input("Flaw Intensity (0-100%)", min_value=0, max_value=100, value=0, step=1)
                    ua_class = c6.selectbox("Classification *", ["", "OK", "DFWO", "DFWR"])
                    
                    if st.form_submit_button("Save New Test", type="primary"):
                        if not all([ua_du, ua_due, ua_loc.strip(), ua_class]):
                            st.error("Please fill all required fields (*)")
                        else:
                            date_str = ua_du.strftime("%d/%m/%Y")
                            is_duplicate = False
                            if not history_df.empty:
                                existing_dates = history_df["Date of USFD testing"].astype(str).str.strip().tolist()
                                if date_str in existing_dates:
                                    is_duplicate = True
                                    
                            if is_duplicate:
                                st.error("❌ Duplicate Blocked! A test for this date already exists.")
                            else:
                                timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                row_data = [
                                    search_clean, date_str, ua_due.strftime("%d/%m/%Y"), 
                                    ua_loc.strip(), ua_flaw, ua_probe, int(ua_int), ua_class,
                                    st.session_state["user"], timestamp, "Initial Entry"
                                ]
                                usfd_sheet.append_row(row_data)
                                st.success("✅ New test logged!")
            
            elif action == "Edit a Past Test":
                if history_df.empty:
                    st.warning("No past tests available.")
                else:
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
                        val_int = safe_int(d.get("Flaw Intensity", 0))
                        ue_int = c5.number_input("Flaw Intensity (0-100%)", min_value=0, max_value=100, value=val_int, step=1)
                        
                        class_opts = ["", "OK", "DFWO", "DFWR"]
                        ue_class = c6.selectbox("Classification *", class_opts, index=class_opts.index(d.get("Classification")) if d.get("Classification") in class_opts else 0)
                        
                        st.markdown("---")
                        ue_reason = st.text_input("Reason for Modification (Required for Audit Trail) *", placeholder="e.g. Correcting typo")
                        
                        if st.form_submit_button("Update & Log Audit", type="primary"):
                            if not all([ue_du, ue_due, ue_loc.strip(), ue_class, ue_reason.strip()]):
                                st.error("Please fill all required fields and provide a Reason for Modification.")
                            else:
                                timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                row_data = [
                                    search_clean, ue_du.strftime("%d/%m/%Y"), ue_due.strftime("%d/%m/%Y"), 
                                    ue_loc.strip(), ue_flaw, ue_probe, int(ue_int), ue_class,
                                    st.session_state["user"], timestamp, ue_reason.strip()
                                ]
                                row_num = int(sel_idx) + 2
                                usfd_sheet.update(f"A{row_num}:K{row_num}", [row_data])
                                st.success("✅ Historical record updated and audit trail logged!")

            elif action == "Delete a Past Test":
                if history_df.empty:
                    st.warning("No past tests available to delete.")
                else:
                    del_opts = {idx: f"Test Date: {row['Date of USFD testing']} | Class: {row.get('Classification','')}" for idx, row in history_df.iterrows()}
                    sel_del_idx = st.selectbox("Select Test to Permanently Delete:", options=list(del_opts.keys()), format_func=lambda x: del_opts[x])
                    
                    st.warning("⚠️ Warning: This will permanently delete only this specific test record.")
                    if st.button("Delete Selected Test", type="primary"):
                        row_num = int(sel_del_idx) + 2
                        usfd_sheet.delete_rows(row_num)
                        st.success("🗑️️ Specific test record successfully deleted!")

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
            st.markdown("Edit fields below. Leave unchanged to keep current data.")
            c1, c2, c3, c4 = st.columns(4)
            m_dw = c1.date_input("Date of Welding *", value=parse_date(d.get("Date of Welding")), min_value=MIN_DATE, format="DD/MM/YYYY")
            m_loc = c2.text_input("Location *", value=str(d.get("Location", "")))
            
            ml_opts = ["", "Main", "Loop"]
            m_ml = c3.selectbox("Main/Loop *", ml_opts, index=ml_opts.index(d.get("Main/Loop")) if d.get("Main/Loop") in ml_opts else 0)
            
            lh_opts = ["", "LH", "RH"]
            m_lhrh = c4.selectbox("LH/RH *", lh_opts, index=lh_opts.index(d.get("LH/RH")) if d.get("LH/RH") in lh_opts else 0)
            
            c5, c6, c7 = st.columns(3)
            m_sec = c5.text_input("Section *", value=str(d.get("Section", "")))
            
            rail_opts = ["", "52KG", "60KG"]
            db_rail = str(d.get("Rail Details", ""))
            m_rail = c6.selectbox("Rail Details *", rail_opts, index=rail_opts.index(db_rail) if db_rail in rail_opts else 0)
            m_rm = c7.text_input("Rolling Mark", value=str(d.get("Rolling Mark", "")))

            c8, c9, c10, c11, c11b = st.columns([1.5, 2, 1, 1, 1])
            ag_opts = ["", "ITC", "CKD", "OBOROI", "TPP", "SAGAR", "OTHER"]
            db_ag = str(d.get("Agency Code", ""))
            ag_idx = ag_opts.index(db_ag) if db_ag in ag_opts else ag_opts.index("OTHER") if db_ag else 0
            m_ag_sel = c8.selectbox("Agency Code", ag_opts, index=ag_idx)
            m_ag_oth = c8.text_input("Specify Agency", value=db_ag if ag_idx == 6 else "") if m_ag_sel == "OTHER" else ""
            m_ag = m_ag_oth if m_ag_sel == "OTHER" else m_ag_sel

            sup_opts = ["", "JE/MMG/CHI", "JE/MMG/RN", "JE/MMG/RAJP", "JE/MMG/KUDL", "Other"]
            db_sup = str(d.get("Supervisor Code", ""))
            sup_idx = sup_opts.index(db_sup) if db_sup in sup_opts else sup_opts.index("Other") if db_sup else 0
            m_sup_sel = c9.selectbox("Supervisor Code", sup_opts, index=sup_idx)
            m_sup_oth = c9.text_input("Specify Supervisor", value=db_sup if sup_idx == 5 else "") if m_sup_sel == "Other" else ""
            m_sup = m_sup_oth if m_sup_sel == "Other" else m_sup_sel

            m_welder = c10.number_input("Welder Code", min_value=0, step=1, value=safe_int(d.get("Welder Code", 0)))
            
            db_weldno = str(d.get("Weld No.", ""))
            pfx_val = "LH" if "LH" in db_weldno.upper() else "RN"
            num_val = safe_int(re.sub(r'\D', '', db_weldno))
            m_weldno_pfx = c11.selectbox("Weld Pfx", ["LH", "RN"], index=["LH", "RN"].index(pfx_val))
            m_weldno_num = c11b.number_input("Weld No. (INT)", min_value=0, step=1, value=num_val)
            m_weldno = f"{m_weldno_pfx}{m_weldno_num}"
            
            c12, c13, c14 = st.columns(3)
            m_port = c12.text_input("Portion No.", value=str(d.get("Portion No", "")))
            m_batch = c13.text_input("Batch No.", value=str(d.get("Batch No", "")))
            m_dpm = c14.date_input("Date of Portion Mfg", value=parse_date(d.get("Date of Portion Mfg")), min_value=MIN_DATE, format="DD/MM/YYYY")

            c15, c16, c17, c18 = st.columns(4)
            m_rt = c15.number_input("Reaction Time (sec)", min_value=0, step=1, value=safe_int(d.get("Reaction Time (sec)", 0)))
            m_bf = c16.number_input("Block Time From (HHMM)", min_value=0, max_value=2359, step=1, value=safe_int(d.get("Block Time From", 0)))
            m_bt = c17.number_input("Block Time To (HHMM)", min_value=0, max_value=2359, step=1, value=safe_int(d.get("Block Time To", 0)))
            m_fg = c18.number_input("Finishing/Grinding Time (HHMM)", min_value=0, max_value=2359, step=1, value=safe_int(d.get("Finishing & Grinding Time", 0)))
            
            c19, c20, c21 = st.columns(3)
            m_mw = c19.number_input("Mould Waiting Time (min)", min_value=0, step=1, value=safe_int(d.get("Mould Waiting Time (min)", 0)))
            m_ph = c20.number_input("Pre-heating Time (min)", min_value=0, step=1, value=safe_int(d.get("Pre-heating Time (min)", 0)))
            m_tp = c21.number_input("Time 1st Train Passed (HHMM)", min_value=0, max_value=2359, step=1, value=safe_int(d.get("Time 1st Train Passed", 0)))

            c22, c23, c24, c25 = st.columns(4)
            m_1mt = c22.number_input("1m Top (mm)", step=1, value=safe_int(d.get("1m Top Tolerance", 0)))
            m_1ms = c23.number_input("1m Side (mm)", step=1, value=safe_int(d.get("1m Side Tolerance", 0)))
            m_10cv = c24.number_input("10cm Vert (mm)", step=1, value=safe_int(d.get("10cm Vert Tolerance", 0)))
            m_10cl = c25.number_input("10cm Lat (mm)", step=1, value=safe_int(d.get("10cm Lat Tolerance", 0)))

            if st.form_submit_button("Update MMG Record", type="primary"):
                month = m_dw.strftime("%m")
                year_yy = m_dw.strftime("%y")
                rdso_mark = f"{month}-{year_yy}-{m_ag.strip().upper()}-{m_welder}-{m_weldno}"
                
                timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                dpm_str = m_dpm.strftime("%d/%m/%Y") if m_dpm else ""

                updated_values = [
                    str(d.get("AT weld ID")), m_dw.strftime("%d/%m/%Y"), m_loc.strip(), m_ml, m_lhrh, 
                    m_sec.strip(), m_rail.strip(), m_port.strip(), m_batch.strip(), m_rm.strip(), 
                    m_ag.strip().upper(), m_sup.strip(), int(m_welder), m_weldno, dpm_str, 
                    int(m_rt), int(m_bf), int(m_bt), int(m_fg), int(m_mw), 
                    int(m_ph), int(m_1mt), int(m_1ms), int(m_10cv), int(m_10cl), 
                    int(m_tp), rdso_mark, st.session_state["user"], timestamp
                ]
                row_num = st.session_state['mod_weld_row']
                weld_sheet.update(f"A{row_num}:AC{row_num}", [updated_values])
                st.success(f"✅ MMG Record updated! New RDSO Mark: {rdso_mark}")
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
            
            if not usfd_df.empty and "AT weld ID" in usfd_df.columns and del_clean in usfd_df["AT weld ID"].astype(str).values:
                usfd_indices = usfd_df[usfd_df["AT weld ID"].astype(str) == del_clean].index.tolist()
                for idx in sorted(usfd_indices, reverse=True):
                    usfd_sheet.delete_rows(int(idx) + 2)
                st.success(f"🗑️️ Deleted {len(usfd_indices)} historical tests from USFD Database.")
                deleted_something = True
                
            if not weld_df.empty and del_clean in weld_df["AT weld ID"].astype(str).values:
                row_idx = weld_df[weld_df["AT weld ID"].astype(str) == del_clean].index[0]
                weld_sheet.delete_rows(int(row_idx) + 2)
                st.success(f"🗑️ Deleted Master Record '{del_clean}' from Weld Database.")
                deleted_something = True
                
            if not deleted_something:
                st.error(f"Record '{del_clean}' not found in any database.")

# ---------------------------------------------------------
# TAB 5: VIEW DATABASES & DYNAMIC REPORTS
# ---------------------------------------------------------
with tab5:
    st.subheader("Live Databases & Jurisdiction Reports")
    
    weld_df = get_weld_df()
    usfd_df = get_usfd_df()
    
    if not weld_df.empty:
        weld_df["KM_Value"] = weld_df["Location"].apply(extract_km)
        
        st.markdown("### 📍 Filter by Engineering Jurisdiction")
        
        selected_jurisdiction = st.selectbox("Select Jurisdiction:", list(JE_OPTIONS.keys()))
        min_km, max_km = JE_OPTIONS[selected_jurisdiction]
        
        if selected_jurisdiction == "All Division (Complete)":
            filtered_weld_df = weld_df
        elif selected_jurisdiction == "Unassigned / Invalid KM":
            filtered_weld_df = weld_df[weld_df["KM_Value"] == -1]
        else:
            filtered_weld_df = weld_df[(weld_df["KM_Value"] >= min_km) & (weld_df["KM_Value"] <= max_km)]
            
        display_weld_df = filtered_weld_df.drop(columns=["KM_Value"])
        
        valid_ids = display_weld_df["AT weld ID"].tolist()
        display_usfd_df = usfd_df[usfd_df["AT weld ID"].isin(valid_ids)] if not usfd_df.empty else pd.DataFrame()
            
        st.markdown(f"### 1. MMG Weld Database ({selected_jurisdiction})")
        st.dataframe(display_weld_df, use_container_width=True)
        
        st.markdown(f"### 2. USFD Testing Database History ({selected_jurisdiction})")
        if display_usfd_df.empty: 
            st.info("No USFD test records found for this jurisdiction selection.")
        else: 
            st.dataframe(display_usfd_df, use_container_width=True)
            
        st.markdown("---")
        st.subheader(f"📥 Download Reports for: {selected_jurisdiction}")
        
        col_dl1, col_dl2 = st.columns(2)
        file_prefix = selected_jurisdiction.split(" (")[0].replace("/", "_")
        
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                display_weld_df.to_excel(writer, index=False, sheet_name='Weld_Details')
                if not display_usfd_df.empty:
                    display_usfd_df.to_excel(writer, index=False, sheet_name='USFD_History')
            
            col_dl1.download_button(
                label=f"📊 Download Excel Report ({selected_jurisdiction})",
                data=buffer.getvalue(),
                file_name=f"Weld_Report_{file_prefix}_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            col_dl1.info("⚠️ Ensure 'openpyxl' is in requirements.txt for Excel downloads.")

        col_dl2.download_button(
            label=f"📄 Download Weld CSV ({selected_jurisdiction})",
            data=display_weld_df.to_csv(index=False).encode('utf-8'),
            file_name=f"Weld_Details_{file_prefix}_{datetime.date.today()}.csv",
            mime="text/csv",
        )
    else:
        st.info("The database is currently empty. Add records using the 'Add Weld' tab.")
