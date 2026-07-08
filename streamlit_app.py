from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from app.newsletter_agent.agent import DEFAULT_GOAL, run_newsletter_agent

load_dotenv()

st.set_page_config(
    page_title="Newsletter Agent",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="stApp"] {
    font-family: 'Inter', sans-serif;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #0f1923 0%, #152234 50%, #1a2d42 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

section[data-testid="stSidebar"] * {
    color: #d1d9e6 !important;
}

section[data-testid="stSidebar"] h1 {
    color: #ffffff !important;
    font-weight: 800;
    letter-spacing: -0.5px;
}

section[data-testid="stSidebar"] .stRadio label span {
    font-weight: 600;
}

section[data-testid="stSidebar"] textarea {
    background: rgba(255, 255, 255, 0.06) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    color: #e8edf3 !important;
    border-radius: 8px;
}

section[data-testid="stSidebar"] textarea:focus {
    border-color: #4a9eff !important;
    box-shadow: 0 0 0 2px rgba(74, 158, 255, 0.15) !important;
}

.status-idle {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.08);
    color: #8899aa;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.status-running {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(234, 179, 8, 0.12);
    color: #d4a017;
    border: 1px solid rgba(234, 179, 8, 0.25);
    animation: pulse 1.5s ease-in-out infinite;
}

.status-sent {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.25);
}

.status-review {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(168, 85, 247, 0.1);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.25);
}

.status-error {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.25);
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

.hero-header {
    padding: 28px 0 20px;
    margin-bottom: 16px;
    border-bottom: 1px solid #e5e7eb;
}

.hero-header h1 {
    font-size: 28px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.5px;
    margin: 0 0 4px;
}

.hero-subtitle {
    font-size: 14px;
    color: #6b7280;
    margin: 0;
}

.info-card {
    background: linear-gradient(135deg, #f0f9ff 0%, #e8f4fd 100%);
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 12px 0 20px;
}

.info-card p {
    margin: 0;
    font-size: 14px;
    color: #1e40af;
    line-height: 1.55;
}

.review-card {
    background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%);
    border: 1px solid #fcd34d;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 16px 0;
}

.review-card h3 {
    margin: 0 0 10px;
    color: #92400e;
    font-size: 16px;
    font-weight: 700;
}

.review-card p {
    margin: 0;
    font-size: 14px;
    color: #78350f;
    line-height: 1.55;
    white-space: pre-wrap;
}

.footer-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 20px;
    padding: 18px 22px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

.footer-grid .label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9ca3af;
    margin: 0 0 4px;
}

.footer-grid .value {
    font-size: 14px;
    color: #111827;
    word-break: break-all;
    margin: 0;
}

.tool-log-entry {
    display: block;
    padding: 8px 14px;
    margin: 4px 0;
    background: #f3f4f6;
    border-left: 3px solid #6366f1;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: #374151;
    font-family: 'Inter', sans-serif;
}

.plan-step {
    display: block;
    padding: 8px 14px;
    margin: 4px 0;
    background: #f0fdf4;
    border-left: 3px solid #22c55e;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: #166534;
    font-family: 'Inter', sans-serif;
}

div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 700;
    font-size: 14px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _get_status_html(status: str) -> str:
    """Return styled HTML badge for the current agent status."""
    label_map = {
        "idle": ("Idle", "status-idle"),
        "running": ("Running", "status-running"),
        "sent": ("Sent", "status-sent"),
        "needs_review": ("Awaiting Review", "status-review"),
        "error": ("Error", "status-error"),
    }
    label, css_class = label_map.get(status, ("Idle", "status-idle"))
    return f'<span class="{css_class}">{label}</span>'


def _render_tool_log(plan: list[str], tool_log: list[str]) -> None:
    """Render the plan steps and tool log as styled blocks."""
    if plan:
        st.markdown("##### Agent Plan")
        for index, step in enumerate(plan, start=1):
            st.markdown(
                f'<div class="plan-step"><strong>Step {index}:</strong> {step}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("---")

    if tool_log:
        st.markdown("##### Tool Execution Log")
        for entry in tool_log:
            st.markdown(
                f'<div class="tool-log-entry">{entry}</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Sidebar: Controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("# Newsletter Agent")
    st.markdown(
        '<p style="font-size:13px; opacity:0.7; margin-top:-10px;">'
        "Autonomous AI newsletter generation</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    goal = st.text_area(
        "Goal",
        value=DEFAULT_GOAL,
        height=110,
        help="Describe what the newsletter should cover.",
    )

    mode = st.radio(
        "Mode",
        options=["autonomous", "human"],
        format_func=lambda value: (
            "Fully Autonomous" if value == "autonomous" else "Human-in-the-Loop"
        ),
        horizontal=True,
    )

    human_feedback = None
    if mode == "human":
        human_feedback = st.text_area(
            "Editor Feedback",
            placeholder="Add feedback after reviewing the first draft",
            height=90,
        )

    col_run, col_clear = st.columns(2)
    with col_run:
        run_clicked = st.button("Run Agent", type="primary", use_container_width=True)
    with col_clear:
        clear_clicked = st.button("Clear", use_container_width=True)

    if clear_clicked:
        for key in list(st.session_state.keys()):
            if key.startswith("result"):
                del st.session_state[key]
        st.session_state["agent_status"] = "idle"
        st.rerun()

    st.markdown("---")
    status = st.session_state.get("agent_status", "idle")
    st.markdown(_get_status_html(status), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main: Agent execution
# ---------------------------------------------------------------------------

if run_clicked:
    st.session_state["agent_status"] = "running"

    with st.spinner("The agent is working through its pipeline..."):
        try:
            result = run_newsletter_agent(
                goal=goal,
                mode=mode,
                human_feedback=human_feedback if human_feedback else None,
            )
            st.session_state["result"] = result
            st.session_state["agent_status"] = result.get("status", "sent")
        except Exception as exc:
            st.session_state["agent_status"] = "error"
            st.session_state["result"] = {"error": str(exc)}

    st.rerun()

# ---------------------------------------------------------------------------
# Main: Output display
# ---------------------------------------------------------------------------

result = st.session_state.get("result")

st.markdown(
    '<div class="hero-header">'
    "<h1>Newsletter Agent</h1>"
    '<p class="hero-subtitle">Autonomous research, summarization, and newsletter generation</p>'
    "</div>",
    unsafe_allow_html=True,
)

if result is None:
    st.markdown(
        '<div class="info-card">'
        "<p>Configure a goal and mode in the sidebar, then press "
        "<strong>Run Agent</strong> to generate a newsletter.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

if "error" in result:
    st.error(f"Agent error: {result['error']}")
    st.stop()

# Human review panel
if result.get("needs_human_review"):
    critique = result.get("critique", "Review the draft before finalizing.")
    st.markdown(
        '<div class="review-card">'
        "<h3>Human Review Required</h3>"
        f"<p>{critique}</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.info(
        "Switch to **Human-in-the-Loop** mode in the sidebar, enter your "
        "feedback, and press **Run Agent** again to finalize."
    )

# Tabbed output
tab_preview, tab_markdown, tab_log = st.tabs(["Preview", "Markdown", "Tool Log"])

with tab_preview:
    html_content = result.get("html", "")
    if html_content:
        st.components.v1.html(html_content, height=700, scrolling=True)
    else:
        st.info("No HTML preview available yet.")

with tab_markdown:
    md_content = result.get("markdown", "")
    if md_content:
        st.code(md_content, language="markdown")
    else:
        st.info("No markdown content available yet.")

with tab_log:
    _render_tool_log(
        result.get("plan", []),
        result.get("tool_log", []),
    )
    revision_notes = result.get("revision_notes", [])
    if revision_notes:
        st.markdown("##### Revision Notes")
        for note in revision_notes:
            st.markdown(f"- {note}")

# Footer metadata
subject = result.get("subject", "")
output_paths = result.get("output_paths", {})
paths_text = " | ".join(
    f"{kind}: {path}" for kind, path in output_paths.items()
) if output_paths else "Not saved yet"

st.markdown(
    '<div class="footer-grid">'
    "<div>"
    '<p class="label">Subject</p>'
    f'<p class="value">{subject or "Draft generated"}</p>'
    "</div>"
    "<div>"
    '<p class="label">Saved Files</p>'
    f'<p class="value">{paths_text}</p>'
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)
