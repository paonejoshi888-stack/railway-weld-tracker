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

JE_OPTIONS = {
    "All Division (Complete)": (-1, 9999), "DEN/CHI (Km 0-154)": (0, 154),
    "SSE/MNI (Km 0-79)": (0, 79), "SSE/CHI (Km 80-154)": (80, 154),
    "JE/KOL (Km 0-23)": (0, 23), "JE/VEER (Km 24-46)": (24, 46),
    "JE/KFD (Km 47-79)": (47, 79), "JE/KHED (Km 80-119)": (80, 119),
    "JE/CHI (Km 120-154)": (120, 154), "DEN/KKW (Km 226-378)": (226, 378),
    "SSE/Sec/RN (Km 191-226)": (191, 226), "SSE/P/RN (Km 154-226)": (154, 226),
    "AEN/RN (Km 154-226)": (154, 226), "SSE/VID (Km 226-299)": (226, 299),
    "SSE/KKW (Km 299-371)": (299, 371), "JE/SGR (Km 154-191)": (154, 191),
    "JE/ADVI (Km 226-258)": (226, 258), "JE/VBW (Km 258-299)": (258, 299),
    "JE/KKW (Km 299-337)": (299, 337), "JE/SWV (Km 337-371)": (337, 371),
    "Unassigned / Invalid KM": (-1, -1)
}

SECTION_OPTIONS = [
    "", "ROHA-KOL", "KOL-INP", "INP-MNI", "MNI-GNO", "GNO-VEER", "VEER-SAPE", 
    "SAPE-KFD", "KFD-VINH", "VINH-DWV", "DWV-KLBN", "KLBN-KHED", "KHED-ANO", 
    "ANO-CHI", "CHI-KMAH", "KMAH-SVX", "SVX-AVRD", "AVRD-KDVI", "KDVI-SGR", 
    "SGR-UKC", "UKC-BHOKE", "BHOKE-RN", "RN-NIV", "NIV-ADVI", "ADVI-VRLI", 
    "VRLI-VID", "VID-RAJP", "RAJP-KRPN", "KRPN-VBW", "VBW-ACRN", "ACRN-NAN", 
    "NAN-KKW", "KKW-SNDD", "SNDD-KUDL", "KUDL-ZARP", "ZARP-SWV", "SWV-MADR", "MADR-PERN"
]

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

def safe_float(val):
    try: return float(val)
    except: return 0.0

def parse_time_val(val):
    if val is None or pd.isna(val) or str(val).strip() == "": return 0, 0
    val_str = str(val).strip()
    if ":" in val_str:
        parts = val_str.split(":")
        try: return int(parts[0]), int(parts[1])
        except: return 0, 0
    else:
        try:
            v = int(float(val_str))
            return v // 100, v % 100
        except: return 0, 0

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
    return wb.worksheet("WeldDetails"), wb.worksheet("USFDDetails"), wb.worksheet("RailTestLogs"), wb.worksheet("RailDefects")

try:
    weld_sheet, usfd_sheet, rail_logs_sheet, rail_defects_sheet = init_connection()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Check if 'RailTestLogs' and 'RailDefects' tabs exist. Error: {e}")
    st.stop()

def get_weld_df(): return pd.DataFrame(weld_sheet.get_all_records())
def get_usfd_df(): return pd.DataFrame(usfd_sheet.get_all_records())
def get_rail_logs_df(): 
    try: return pd.DataFrame(rail_logs_sheet.get_all_records())
    except: return pd.DataFrame()
def get_rail_defects_df(): 
    try: return pd.DataFrame(rail_defects_sheet.get_all_records())
    except: return pd.DataFrame()

# =========================================================
# TABS SETUP
# =========================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "➕ Add Weld (MMG)", 
    "🩺 Weld USFD", 
    "🛤️ Rail USFD",
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
        add_sec = c5.selectbox("Section *", SECTION_OPTIONS)
        add_rail = c6.selectbox("Rail Details *", ["", "52KG", "60KG"])
        add_rm = c7.text_input("Rolling Mark *")

        st.markdown("**3. Materials & Agency**")
        c8, c9, c10, c11, c11b = st.columns([1.5, 2, 1.5, 1, 1])
        
        ag_opts = ["", "ITC", "CKD", "OBOROI", "TPP", "SAGAR", "OTHER"]
        add_ag_sel = c8.selectbox("Agency Code *", ag_opts)
        add_ag_oth = c8.text_input("Specify Agency (if OTHER)", key="add_ag_oth")
        
        sup_opts = ["", "JE/MMG/CHI", "JE/MMG/RN", "JE/MMG/RAJP", "JE/MMG/KUDL", "JE/MMG/VEER", "Other"]
        add_sup_sel = c9.selectbox("Supervisor Code *", sup_opts)
        add_sup_oth = c9.text_input("Specify Supervisor (if Other)", key="add_sup_oth")
        
        add_welder = c10.text_input("Welder Code *", placeholder="e.g. 104, W1")
        
        add_weldno_pfx = c11.selectbox("Weld Pfx *", ["LH", "RH"])
        add_weldno_num = c11b.number_input("Weld No. (INT) *", min_value=0, step=1, value=0)
        
        c12, c13, c14 = st.columns(3)
        add_port = c12.text_input("Portion No.")
        add_batch = c13.text_input("Batch No.")
        add_dpm = c14.date_input("Date of Portion Mfg", value=None, min_value=MIN_DATE, format="DD/MM/YYYY")

        st.markdown("**4. Execution Timings**")
        c_rt, c_mw, c_ph = st.columns(3)
        add_rt = c_rt.number_input("Reaction Time (sec) [INT]", min_value=0, step=1, value=0)
        add_mw = c_mw.number_input("Mould Waiting Time (min) [INT]", min_value=0
