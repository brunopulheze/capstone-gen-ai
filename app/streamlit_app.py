"""
BrixoAI Capstone — Streamlit Chat Interface
============================================
Single-chatbox UI modelled after the original BrixoAI chatbot widget.
All services are accessed through the chat flow — service buttons, guided
step chips, and file uploads are surfaced inline.

Run with:
    streamlit run app/streamlit_app.py
"""

import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BrixoAI",
    page_icon="🤖",
    layout="centered",
)

# ── Constants ─────────────────────────────────────────────────────────────────
GREETING = (
    "Hi there! I'm BrixoAI 🐾 Ask me anything about the studio, our services, "
    "or your next project!"
)

SCOPE_QUESTIONS = [
    "First, tell us about your business. What industry or type of business is this for?",
    "What kind of project are you looking to build?",
    "Which features do you need? Select all that apply, then click **Continue**.",
    "Anything else we should know? Describe your project in your own words — "
    "the more detail, the better. Type below and press Enter, or click **Skip**.",
    "When are you hoping to launch?",
]

SCOPE_OPTIONS = [
    [
        "Retail & E-commerce", "Food & Hospitality", "Health & Wellness",
        "Finance & Fintech", "Legal & Consulting", "Education & Coaching",
        "Real Estate", "Creative & Media", "Non-profit", "Technology / SaaS", "Other",
    ],
    [
        "Web App", "Mobile App", "Dashboard / Analytics", "AI / ML Tool",
        "Chatbot / AI Assistant", "E-commerce Store", "Landing Page", "Other",
    ],
    [
        "User Login / Auth", "Payments", "Booking / Scheduling", "Admin Dashboard",
        "Analytics", "Notifications", "File Uploads", "API Integration", "Other",
    ],
    ["As soon as possible", "1-3 months", "3-6 months", "6+ months", "Not sure yet"],
]

PERSONA_QUESTIONS = [
    "What type of product or service is this persona for?",
    "Who is the target audience?",
    "What are their primary goals? Select all that apply, then click **Continue**.",
    "What's their biggest frustration or pain point?",
    "What gender should this persona be?",
]

PERSONA_OPTIONS = [
    [
        "E-commerce Store", "Mobile App", "SaaS / Dashboard", "Healthcare Platform",
        "Educational Platform", "B2B Tool", "Consumer Service", "Other",
    ],
    [
        "Young Adults (18-25)", "Millennials (26-35)", "Gen X (36-50)", "Seniors (50+)",
        "Business Professionals", "Parents", "Students", "General Public", "Other",
    ],
    [
        "Save time", "Save money", "Stay informed", "Get things done",
        "Learn & grow", "Stay healthy", "Connect with others", "Make better decisions", "Other",
    ],
    [
        "Too complicated", "Too slow", "Too expensive", "Hard to find info",
        "Not mobile-friendly", "Poor onboarding", "Lack of trust", "Limited features", "Other",
    ],
    ["Female", "Male", "Non-binary"],
]

SERVICES = [
    {"mode": "chat",          "label": "💬 Chat",          "desc": "Conversational assistant with RAG"},
    {"mode": "data-insights", "label": "📊 Data Insights", "desc": "Analyze CSV/Excel files"},
    {"mode": "ux-audit",      "label": "🎨 UX Audit",      "desc": "Audit a URL or UI screenshot"},
    {"mode": "scope-project", "label": "💼 Scope Project", "desc": "Guided project scoping"},
    {"mode": "user-persona",  "label": "👤 User Persona",  "desc": "Generate UX user personas"},
]

# ── Session state defaults ────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "messages":         [{"role": "assistant", "content": GREETING}],
        "svc_mode":         None,
        "show_svcs":        True,
        # Scope Project flow
        "scope_step":       None,
        "scope_answers":    {
            "business_type": "", "project_type": "", "features": [],
            "timeline": "", "description": "", "brand_preferences": "",
        },
        "pending_features": [],
        # User Persona flow
        "persona_step":     None,
        "persona_answers":  {
            "product_type": "", "audience": "", "goals": [],
            "frustration": "", "gender": "",
        },
        "pending_goals":    [],
        # Data Insights Q&A context
        "dataset_ctx":      "",
        # File uploader version keys (incrementing resets the widget)
        "di_ver":           0,
        "ux_ver":           0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Message helpers ────────────────────────────────────────────────────────────
def _bot(content: str):
    st.session_state.messages.append({"role": "assistant", "content": content})

def _user(content: str):
    st.session_state.messages.append({"role": "user", "content": content})

def _activate(mode: str, prompt: str):
    st.session_state.svc_mode = mode
    st.session_state.show_svcs = False
    _bot(prompt)

# ── Scope: format report dict as markdown ─────────────────────────────────────
def _format_scope(reply: str, scope: dict) -> str:
    parts = [f"✅ **{reply or 'Scope ready!'}**\n"]
    parts.append(f"### 📋 {scope.get('project_type', 'Project Scope')}\n{scope.get('overview', '')}")
    if scope.get("features"):
        parts.append("**🚀 Features:**\n" + "\n".join(f"• {f}" for f in scope["features"]))
    if scope.get("tech_stack"):
        parts.append("**⚙️ Tech Stack:**\n" + "\n".join(f"• {t}" for t in scope["tech_stack"]))
    if scope.get("timeline"):
        parts.append(f"**⏱️ Timeline:** {scope['timeline']}")
    if scope.get("next_steps"):
        parts.append("**📌 Next Steps:**\n" + "\n".join(f"• {s}" for s in scope["next_steps"]))
    return "\n\n".join(parts)

# ── Persona: format report dict as markdown ───────────────────────────────────
def _format_persona(reply: str, persona: dict) -> str:
    parts = [f"✅ **{reply or 'Persona ready!'}**\n"]
    parts.append(
        f"### 👤 {persona.get('name', 'Persona')} "
        f"— {persona.get('age', '')} · {persona.get('role', '')} · {persona.get('location', '')}"
    )
    if persona.get("quote"):
        parts.append(f"> 💬 *\"{persona['quote']}\"*")
    if persona.get("bio"):
        parts.append(persona["bio"])
    if persona.get("goals"):
        parts.append("**🎯 Goals:**\n" + "\n".join(f"✅ {g}" for g in persona["goals"]))
    if persona.get("pain_points"):
        parts.append("**😤 Pain Points:**\n" + "\n".join(f"❌ {p}" for p in persona["pain_points"]))
    if persona.get("motivations"):
        parts.append("**💡 Motivations:**\n" + "\n".join(f"💙 {m}" for m in persona["motivations"]))
    return "\n\n".join(parts)

# ── Backend helper ─────────────────────────────────────────────────────────────

def _post(endpoint: str, **kwargs) -> dict:
    try:
        r = requests.post(f"{API_BASE}{endpoint}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"reply": f"⚠️ Cannot reach the API at {API_BASE}. Is the FastAPI server running?"}
    except Exception as e:
        return {"reply": f"⚠️ Error: {str(e)}"}

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🤖 BrixoAI")
    st.caption("Capstone Demo · Gen AI")
    st.divider()
    if st.button("🔄 Reset chat", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.divider()
    st.caption("Powered by LangChain · Groq · ChromaDB · Tavily")

# ══════════════════════════════════════════════════════════════════════════════
#  CHAT HISTORY
# ══════════════════════════════════════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ══════════════════════════════════════════════════════════════════════════════
#  SERVICE BUTTONS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_svcs:
    cols = st.columns(3)
    for i, svc in enumerate(SERVICES):
        with cols[i % 3]:
            if st.button(
                svc["label"],
                help=svc["desc"],
                key=f"svc_{svc['mode']}",
                use_container_width=True,
            ):
                mode = svc["mode"]
                if mode == "scope-project":
                    st.session_state.scope_step = 0
                    st.session_state.scope_answers = {
                        "business_type": "", "project_type": "", "features": [],
                        "timeline": "", "description": "", "brand_preferences": "",
                    }
                    st.session_state.pending_features = []
                    _activate(
                        "scope-project",
                        "Let's scope your project! 🐾 I'll guide you through 5 quick questions.\n\n"
                        f"**Step 1 of 5:** {SCOPE_QUESTIONS[0]}",
                    )
                elif mode == "user-persona":
                    st.session_state.persona_step = 0
                    st.session_state.persona_answers = {
                        "product_type": "", "audience": "", "goals": [],
                        "frustration": "", "gender": "",
                    }
                    st.session_state.pending_goals = []
                    _activate(
                        "user-persona",
                        "Let's create a user persona in 5 quick steps! 🐾\n\n"
                        f"**Step 1 of 5:** {PERSONA_QUESTIONS[0]}",
                    )
                elif mode == "chat":
                    _activate("chat", "I'm in **Chat** mode now. Ask me anything about the studio, services, or your next project!")
                elif mode == "data-insights":
                    _activate("data-insights", "Let's analyze your data! 📊 Upload a CSV or Excel file below and I'll find key patterns, trends, and insights.")
                elif mode == "ux-audit":
                    _activate("ux-audit", "Ready to audit your UI! 🎨 Use the tabs below to paste a URL or upload a screenshot.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  ACTIVE MODE PILL
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.svc_mode:
    svc_label = next((s["label"] for s in SERVICES if s["mode"] == st.session_state.svc_mode), "")
    pill_l, pill_r = st.columns([5, 1])
    with pill_l:
        st.caption(f"Active: **{svc_label}**")
    with pill_r:
        if st.button("← Services", key="back_svcs"):
            st.session_state.svc_mode = None
            st.session_state.show_svcs = True
            st.session_state.scope_step = None
            st.session_state.scope_answers = {
                "business_type": "", "project_type": "", "features": [],
                "timeline": "", "description": "", "brand_preferences": "",
            }
            st.session_state.pending_features = []
            st.session_state.persona_step = None
            st.session_state.persona_answers = {
                "product_type": "", "audience": "", "goals": [],
                "frustration": "", "gender": "",
            }
            st.session_state.pending_goals = []
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  SCOPE PROJECT — guided chip panels
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.svc_mode == "scope-project" and isinstance(st.session_state.scope_step, int):
    step = st.session_state.scope_step
    st.caption(f"Step {step + 1} of 5")
    st.divider()

    if step == 2:
        pending = st.session_state.pending_features
        chip_cols = st.columns(3)
        for i, opt in enumerate(SCOPE_OPTIONS[2]):
            with chip_cols[i % 3]:
                active = opt in pending
                if st.button(f"{'✅ ' if active else ''}{opt}", key=f"feat_{i}", use_container_width=True):
                    if active:
                        st.session_state.pending_features.remove(opt)
                    else:
                        st.session_state.pending_features.append(opt)
                    st.rerun()
        if pending:
            if st.button(f"Continue ({len(pending)} selected) →", key="feat_continue", type="primary"):
                _user(", ".join(pending))
                st.session_state.scope_answers["features"] = list(pending)
                st.session_state.pending_features = []
                st.session_state.scope_step = 3
                _bot(f"**Step 4 of 5:** {SCOPE_QUESTIONS[3]}")
                st.rerun()

    elif step == 3:
        if st.button("Skip this step →", key="scope_skip_desc"):
            _user("*(skipped)*")
            st.session_state.scope_answers["description"] = ""
            st.session_state.scope_step = 4
            _bot(f"**Step 5 of 5:** {SCOPE_QUESTIONS[4]}")
            st.rerun()

    elif step == 4:
        chip_cols = st.columns(3)
        for i, opt in enumerate(SCOPE_OPTIONS[3]):
            with chip_cols[i % 3]:
                if st.button(opt, key=f"tl_{i}", use_container_width=True):
                    _user(opt)
                    st.session_state.scope_answers["timeline"] = opt
                    st.session_state.scope_step = "done"
                    answers = st.session_state.scope_answers
                    with st.spinner("Generating your scope document… 🐾"):
                        data = _post("/scope-project", json={
                            "business_type":    answers["business_type"],
                            "project_type":     answers["project_type"],
                            "features":         answers["features"],
                            "timeline":         answers["timeline"],
                            "description":      answers["description"],
                            "brand_preferences": answers["brand_preferences"],
                        })
                    if data.get("scope_report"):
                        _bot(_format_scope(data.get("reply", ""), data["scope_report"]))
                    else:
                        _bot(data.get("reply", "Something went wrong — please try again."))
                    st.rerun()

    else:
        chip_cols = st.columns(3)
        for i, opt in enumerate(SCOPE_OPTIONS[step]):
            with chip_cols[i % 3]:
                if st.button(opt, key=f"scope_{step}_{i}", use_container_width=True):
                    _user(opt)
                    if step == 0:
                        st.session_state.scope_answers["business_type"] = opt
                        st.session_state.scope_step = 1
                        _bot(f"**Step 2 of 5:** {SCOPE_QUESTIONS[1]}")
                    else:
                        st.session_state.scope_answers["project_type"] = opt
                        st.session_state.scope_step = 2
                        _bot(f"**Step 3 of 5:** {SCOPE_QUESTIONS[2]}")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  USER PERSONA — guided chip panels
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.svc_mode == "user-persona" and isinstance(st.session_state.persona_step, int):
    step = st.session_state.persona_step
    st.caption(f"Step {step + 1} of 5")
    st.divider()

    if step == 2:
        pending = st.session_state.pending_goals
        chip_cols = st.columns(3)
        for i, opt in enumerate(PERSONA_OPTIONS[2]):
            with chip_cols[i % 3]:
                active = opt in pending
                if st.button(f"{'✅ ' if active else ''}{opt}", key=f"goal_{i}", use_container_width=True):
                    if active:
                        st.session_state.pending_goals.remove(opt)
                    else:
                        st.session_state.pending_goals.append(opt)
                    st.rerun()
        if pending:
            if st.button(f"Continue ({len(pending)} selected) →", key="goals_continue", type="primary"):
                _user(", ".join(pending))
                st.session_state.persona_answers["goals"] = list(pending)
                st.session_state.pending_goals = []
                st.session_state.persona_step = 3
                _bot(f"**Step 4 of 5:** {PERSONA_QUESTIONS[3]}")
                st.rerun()

    elif step == 4:
        chip_cols = st.columns(3)
        for i, opt in enumerate(PERSONA_OPTIONS[4]):
            with chip_cols[i % 3]:
                if st.button(opt, key=f"gender_{i}", use_container_width=True):
                    _user(opt)
                    st.session_state.persona_answers["gender"] = opt.lower()
                    st.session_state.persona_step = "done"
                    answers = st.session_state.persona_answers
                    goals = answers.get("goals", [])
                    if isinstance(goals, str):
                        goals = [g.strip() for g in goals.split(",") if g.strip()]
                    with st.spinner("Generating your persona… 🐾"):
                        data = _post("/persona", json={
                            "product_type": answers["product_type"],
                            "audience":     answers["audience"],
                            "goals":        goals,
                            "frustration":  answers["frustration"],
                            "gender":       opt.lower(),
                        })
                    if data.get("persona_report"):
                        _bot(_format_persona(data.get("reply", ""), data["persona_report"]))
                    else:
                        _bot(data.get("reply", "Something went wrong — please try again."))
                    st.rerun()

    else:
        chip_cols = st.columns(3)
        for i, opt in enumerate(PERSONA_OPTIONS[step]):
            with chip_cols[i % 3]:
                if st.button(opt, key=f"persona_{step}_{i}", use_container_width=True):
                    _user(opt)
                    field_map = {0: "product_type", 1: "audience", 3: "frustration"}
                    if step in field_map:
                        st.session_state.persona_answers[field_map[step]] = opt
                    next_step = step + 1
                    st.session_state.persona_step = next_step
                    _bot(f"**Step {next_step + 1} of 5:** {PERSONA_QUESTIONS[next_step]}")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  DATA INSIGHTS — file uploader widget
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.svc_mode == "data-insights":
    uploaded = st.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xls", "xlsx"],
        key=f"di_upload_{st.session_state.di_ver}",
    )
    if uploaded:
        _user(f"📎 {uploaded.name}")
        with st.spinner("Analysing your dataset… 🐾"):
            data = _post(
                "/upload",
                files={"file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")},
                data={
                    "message": "Analyze this file and highlight key patterns, trends, and insights.",
                    "service_mode": "data-insights",
                    "history": "[]",
                },
            )
        insights = data.get("insights")
        reply_text = data.get("reply", "Analysis complete!")
        if insights:
            st.session_state.dataset_ctx = json.dumps({
                "kpis":         insights.get("kpis"),
                "columns":      [
                    {"name": c["name"], "kind": c.get("kind"), "unique": c.get("unique")}
                    for c in insights.get("columns", [])
                ],
                "correlations": insights.get("correlations"),
                "preview":      insights.get("preview"),
            })
            parts = [reply_text]
            kpis = insights.get("kpis") or []
            if kpis:
                parts.append("**📈 Key Metrics:** " + "  |  ".join(f"{k['label']}: **{k['value']}**" for k in kpis))
            if insights.get("ai_summary"):
                parts.append(f"**🤖 AI Summary:** {insights['ai_summary']}")
            if insights.get("correlations"):
                top = insights["correlations"][:4]
                corr_lines = "\n".join(
                    f"{'🔵' if c['r'] > 0 else '🔴'} **{c['col_a']}** ↔ **{c['col_b']}** (r = {c['r']:.3f})"
                    for c in top
                )
                parts.append(f"**🔗 Top Correlations:**\n{corr_lines}")
            if insights.get("suggested_questions"):
                qs = "\n".join(f"• {q}" for q in insights["suggested_questions"][:3])
                parts.append(f"**💡 Suggested Questions:**\n{qs}")
            parts.append("Feel free to ask follow-up questions about your data below!")
            _bot("\n\n".join(parts))
        else:
            _bot(reply_text)
        st.session_state.di_ver += 1
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  UX AUDIT — URL / screenshot tabs
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.svc_mode == "ux-audit":
    tab_url, tab_img = st.tabs(["🔗 Audit a URL", "🖼️ Audit a Screenshot"])

    with tab_url:
        url_val = st.text_input("Enter a public URL", placeholder="https://example.com", key="ux_url")
        if st.button("Run URL Audit", disabled=not url_val, key="ux_url_btn"):
            _user(f"Audit URL: {url_val}")
            with st.spinner("Scraping and auditing page…"):
                data = _post("/ux-audit/url", data={
                    "url": url_val,
                    "message": "Perform a UX and accessibility audit.",
                    "history": "[]",
                })
            report = data.get("audit_report", "")
            _bot(data.get("reply", "Audit complete!") + ("\n\n" + report if report else ""))
            st.rerun()

    with tab_img:
        img_file = st.file_uploader(
            "Upload a UI screenshot",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"ux_img_{st.session_state.ux_ver}",
        )
        if img_file and st.button("Run Image Audit", key="ux_img_btn"):
            _user(f"🖼️ {img_file.name}")
            with st.spinner("Analysing screenshot with vision model…"):
                data = _post(
                    "/ux-audit/image",
                    files={"file": (img_file.name, img_file.getvalue(), img_file.type)},
                    data={
                        "message": "Perform a UX and accessibility audit of this screenshot.",
                        "history": "[]",
                    },
                )
            report = data.get("audit_report", "")
            _bot(data.get("reply", "Audit complete!") + ("\n\n" + report if report else ""))
            st.session_state.ux_ver += 1
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  CHAT INPUT  (always visible at the bottom)
# ══════════════════════════════════════════════════════════════════════════════
user_input = st.chat_input("Ask me anything…")
if user_input:
    svc = st.session_state.svc_mode
    scope_step = st.session_state.scope_step

    # Scope Project: free-text description (step 3)
    if svc == "scope-project" and scope_step == 3:
        _user(user_input)
        st.session_state.scope_answers["description"] = user_input
        st.session_state.scope_step = 4
        _bot(f"**Step 5 of 5:** {SCOPE_QUESTIONS[4]}")
        st.rerun()

    # Data Insights: follow-up Q&A after a file has been analysed
    elif svc == "data-insights" and st.session_state.dataset_ctx:
        _user(user_input)
        with st.spinner("Thinking…"):
            data = _post("/chat/data", json={
                "message":         user_input,
                "history":         st.session_state.messages[:-1],
                "dataset_context": st.session_state.dataset_ctx,
            })
        _bot(data.get("reply", ""))
        st.rerun()

    # General chat (Chat mode or any other state)
    else:
        _user(user_input)
        with st.spinner("Thinking…"):
            data = _post("/chat", json={
                "message": user_input,
                "history": st.session_state.messages[:-1],
            })
        _bot(data.get("reply", ""))
        if data.get("trigger_service"):
            st.info(f"💡 Service triggered: **{data['trigger_service']}**")
        st.rerun()
