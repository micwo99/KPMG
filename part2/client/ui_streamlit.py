import os
import json
import requests
import streamlit as st
from dotenv import load_dotenv

# ==================== Config ====================
load_dotenv()
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Part 2 – HMO Chatbot (Stateless)",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ==================== Styles (Minimalist) ====================
BASE_CSS = """
<style>
/* CSS to adjust general layout */
.block-container { padding-top: 1.5rem; }
.st-emotion-cache-12fmw11 { /* Targets the chat form */
    padding-bottom: 0 !important;
}
.stTabs [data-testid="st-emotion-cache-1c9v1s6"] { /* Targets the info box */
    margin-bottom: 1.5rem;
}
.rtl { direction: rtl; }
.ltr { direction: ltr; }
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ==================== Stateless client-state ====================
if "lang" not in st.session_state:
    st.session_state.lang = "he"
if "intake_history" not in st.session_state:
    st.session_state.intake_history = []
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "userinfo" not in st.session_state:
    st.session_state.userinfo = {
        "firstName": "", "lastName": "", "id": "", "gender": "",
        "age": 0, "hmo": "", "hmoCard": "", "tier": ""
    }
if "intake_done" not in st.session_state:
    st.session_state.intake_done = False
# New state variable to control the active tab
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "intake"

# ==================== Functions & Translations ====================
def mask_id(s: str):
    s = s or ""
    return ("*"*5 + s[-4:]) if len(s) >= 4 else s

translations = {
    "he": {
        "sidebar_title": "⚙️ הגדרות",
        "sidebar_reset": "אפס 🔁",
        "sidebar_build_index": "בנה אינדקס 🧱",
        "sidebar_summary": "👤 סיכום משתמש",
        "sidebar_name": "שם",
        "sidebar_hmo": "קופה",
        "sidebar_tier": "חבילה",
        "sidebar_gender": "מגדר",
        "sidebar_age": "גיל",
        "sidebar_card": "כרטיס",
        "sidebar_id": "ת.ז.",
        "header_title": "🏥 חלק 2 – צ'אטבוט קופת חולים",
        "header_caption": "רישום (LLM) → שאלות ותשובות על נתונים (עברית/אנגלית)",
        "tab_intake": "רישום",
        "tab_qa": "שאלות",
        "subheader_intake": "שלב 1 – רישום",
        "subheader_qa": "שלב 2 – שאלות ותשובות",
        "info_intake": "אנא ספק פרטים אישיים (שם פרטי ומשפחה, תעודת זהות, גיל, מגדר, קופת חולים, מספר כרטיס וחבילה) דרך הצ'אט. אין טופס — העוזר ינחה אותך שלב-אחר-שלב.",
        "info_qa": "לאחר השלמת שלב הרישום, ניתן לשאול שאלות על הטבות/זכאויות לפי הקופה והחבילה שלך. התשובות מבוססות על המידע שבמסמכי המקור.",
        "warning_not_done": "אנא סיים תחילה את שלב הרישום.",
        "input_intake": "כתוב הודעה...",
        "input_qa": "שאל שאלה על הזכויות שלך...",
        "spinner_thinking": "חושב...",
        "spinner_searching": "מחפש בבסיס הנתונים...",
        "success_intake": "הרישום הושלם בהצלחה ✓",
        "toast_reset": "השיחה אותחלה",
        "toast_answer_ready": "התשובה מוכנה",
        "answer_title": "תשובה",
        "sources_title": "מקורות"
    },
    "en": {
        "sidebar_title": "⚙️ Settings",
        "sidebar_reset": "Reset 🔁",
        "sidebar_build_index": "Build KB index 🧱",
        "sidebar_summary": "👤 User summary",
        "sidebar_name": "Name",
        "sidebar_hmo": "HMO",
        "sidebar_tier": "Tier",
        "sidebar_gender": "Gender",
        "sidebar_age": "Age",
        "sidebar_card": "Card",
        "sidebar_id": "ID",
        "header_title": "🏥 Part 2 – HMO Chatbot",
        "header_caption": "Intake (LLM-led) → Q&A on phase2_data (Heb/Eng)",
        "tab_intake": "Intake",
        "tab_qa": "Q&A",
        "subheader_intake": "Phase 1 – Intake",
        "subheader_qa": "Phase 2 – Q&A",
        "info_intake": "Please provide your details (first/last name, ID, age, gender, HMO, card number, membership tier) via chat. There is no form—the assistant will guide you step by step.",
        "info_qa": "After completing intake, ask about your benefits/coverage based on your HMO and membership tier. Answers are grounded in the provided knowledge base.",
        "warning_not_done": "Finish intake first.",
        "input_intake": "Type a message...",
        "input_qa": "Ask about your HMO benefits...",
        "spinner_thinking": "Thinking...",
        "spinner_searching": "Searching knowledge base...",
        "success_intake": "Intake complete ✓",
        "toast_reset": "Conversation reset",
        "toast_answer_ready": "Answer ready",
        "answer_title": "Answer",
        "sources_title": "Sources"
    }
}
lang = st.session_state.lang
t = translations[lang]

# ==================== Sidebar ====================
with st.sidebar:
    st.markdown(f"### {t['sidebar_title']}")
    st.selectbox("Language / שפה", ["en", "he"], index=0 if lang == "en" else 1, key="lang")

    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button(t['sidebar_reset'], use_container_width=True):
            st.session_state.intake_history = []
            st.session_state.qa_history = []
            st.session_state.intake_done = False
            st.session_state.userinfo = {
                "firstName": "", "lastName": "", "id": "", "gender": "",
                "age": 0, "hmo": "", "hmoCard": "", "tier": ""
            }
            st.session_state.active_tab = "intake" # Reset active tab
            st.toast(t['toast_reset'], icon="♻️")
            st.rerun()
    with col_sb2:
        if st.button(t['sidebar_build_index'], use_container_width=True):
            try:
                with st.spinner("Building KB on server..."):
                    r = requests.post(f"{API_BASE}/build_index", timeout=180)
                st.success(r.json())
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown(f"#### {t['sidebar_summary']}")
    ui = st.session_state.userinfo
    
    st.markdown(f"**{t['sidebar_name']}:** {ui.get('firstName','')} {ui.get('lastName','')}")
    st.markdown(f"**{t['sidebar_hmo']}:** {ui.get('hmo','') or '-'}")
    st.markdown(f"**{t['sidebar_tier']}:** {ui.get('tier','') or '-'}")
    st.markdown(f"**{t['sidebar_gender']}:** {ui.get('gender','') or '-'}")
    st.markdown(f"**{t['sidebar_age']}:** {ui.get('age','') or '-'}")
    st.markdown(f"**{t['sidebar_card']}:** {mask_id(ui.get('hmoCard',''))}")
    st.markdown(f"**{t['sidebar_id']}:** {mask_id(ui.get('id',''))}")

# ==================== Header ====================
st.title(t["header_title"])
st.caption(t["header_caption"])

# Use st.tabs with a key, and select the default tab based on session state
tab1, tab2 = st.tabs([f"{t['tab_intake']} / רישום", f"{t['tab_qa']} / שאלות"])

# ==================== Intake Tab ====================
with tab1:
    st.subheader(t["subheader_intake"])
    st.info(t["info_intake"])

    # Loop to display all messages from the beginning of the history
    for message in st.session_state.intake_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Handle a new user prompt
    if not st.session_state.intake_done:
        prompt = st.chat_input(t["input_intake"], key="intake_input")
        if prompt:
            st.session_state.intake_history.append({"role": "user", "content": prompt})
            st.rerun() # Rerun to display the user message immediately

# ==================== Q&A Tab ====================
with tab2:
    st.subheader(t["subheader_qa"])
    st.info(t["info_qa"])

    if not st.session_state.intake_done:
        st.warning(t["warning_not_done"])
    else:
        # Loop to display all messages from the beginning of the history
        for message in st.session_state.qa_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Handle a new user prompt
        prompt = st.chat_input(t["input_qa"], key="qa_input")
        if prompt:
            st.session_state.qa_history.append({"role": "user", "content": prompt})
            st.rerun() # Rerun to display the user message immediately

# ==================== API Calls after chat inputs ====================
# This section is moved outside the with tab1/with tab2 blocks to ensure it runs
# only once per interaction cycle, regardless of which tab is active.

# This check prevents an infinite loop of reruns
if "processing" not in st.session_state:
    st.session_state.processing = False

if st.session_state.active_tab == "intake" and not st.session_state.intake_done:
    if len(st.session_state.intake_history) > 0 and st.session_state.intake_history[-1]["role"] == "user" and not st.session_state.processing:
        st.session_state.processing = True
        payload = {
            "history": st.session_state.intake_history,
            "user_info": st.session_state.userinfo,
            "lang": lang,
        }
        with st.spinner(t["spinner_thinking"]):
            r = requests.post(f"{API_BASE}/collect", json=payload, timeout=90)
        res = r.json()
        if "detail" in res:
            st.error(res["detail"])
        else:
            assistant_message = res.get("message", "")
            st.session_state.intake_history.append({"role": "assistant", "content": assistant_message})
            st.session_state.userinfo.update(res.get("userinfo", {}))
            if res.get("phase") == "DONE":
                st.session_state.intake_done = True
                st.balloons()
                st.success(t["success_intake"])
                st.session_state.active_tab = "qa" # Switch to Q&A tab
        st.session_state.processing = False
        st.rerun()

elif st.session_state.active_tab == "qa" and st.session_state.intake_done:
    if len(st.session_state.qa_history) > 0 and st.session_state.qa_history[-1]["role"] == "user" and not st.session_state.processing:
        st.session_state.processing = True
        prompt = st.session_state.qa_history[-1]["content"]
        payload = {
            "history": st.session_state.qa_history,
            "user_info": st.session_state.userinfo,
            "question": prompt,
            "lang": lang
        }
        with st.spinner(t["spinner_searching"]):
            r = requests.post(f"{API_BASE}/chat", json=payload, timeout=120)
        res = r.json()
        if "detail" in res:
            st.error(res["detail"])
        else:
            answer = res.get("answer", "")
            sources = res.get("sources", []) or []
            # Format the answer with sources
            full_answer = f"**{t['answer_title']}:** {answer}"
            if sources:
                full_answer += "\n\n---"
                full_answer += f"\n\n**{t['sources_title']}:**"
                for s in sources:
                    full_answer += f"\n- {s}"
            st.session_state.qa_history.append({"role": "assistant", "content": full_answer})
            st.toast(t["toast_answer_ready"], icon="✅")
        st.session_state.processing = False
        st.rerun()