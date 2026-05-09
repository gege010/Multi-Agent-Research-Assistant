"""Streamlit UI for Research Assistant."""
from __future__ import annotations
import streamlit as st
import httpx
import time

API_BASE = "http://localhost:8000"


def init_state():
    defaults = {
        "job_id": None,
        "results": None,
        "status": None,
        "trace_url": None,
        "job_history": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def start_research(query: str, depth: str = "standard") -> str | None:
    try:
        resp = httpx.post(
            f"{API_BASE}/api/v1/research",
            json={"query": query, "depth": depth},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()["job_id"]
        else:
            st.error(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"Connection failed: {e}")
    return None


def poll_status(job_id: str) -> dict:
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/research/{job_id}", timeout=10.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def get_report(job_id: str) -> dict | None:
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/research/{job_id}/report", timeout=30.0)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 409:
            return None  # not ready yet
        else:
            st.warning(f"Report API error: {resp.status_code}")
    except Exception as e:
        st.warning(f"Failed to fetch report: {e}")
    return None


def render_progress(status: str, progress: int, step: str, trace_url: str | None):
    labels = {
        "queued": ("Queued", 5),
        "planning": ("Planning tasks", 20),
        "researching": ("Gathering sources", 50),
        "writing": ("Writing report", 75),
        "reviewing": ("Quality review", 90),
        "done": ("Completed", 100),
        "failed": ("Failed", 100),
    }
    label, pct = labels.get(status, ("Processing...", 0))
    st.progress(pct / 100, text=label)
    col1, col2, col3 = st.columns(3)
    col1.metric("Status", status.capitalize())
    col2.metric("Progress", f"{pct}%")
    col3.metric("Step", step)
    if trace_url:
        st.link_button("View LangSmith Trace", trace_url, type="secondary")


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="wide",
    menu_items={
        "About": "Multi-Agent Research Assistant powered by LangGraph + Groq",
    },
)

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #16213e; margin-bottom: 0.25rem; }
    .sub-header  { color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .done-badge { background: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
    .fail-badge { background: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

init_state()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🔬 Multi-Agent Research Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Powered by LangGraph · Groq Llama-3.3 70B · Tavily + ArXiv search</div>', unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    depth = st.selectbox("Research Depth", ["quick", "standard", "deep"], index=1)
    include_web = st.checkbox("🌐 Web Search (Tavily)", value=True)
    include_arxiv = st.checkbox("📄 Academic Search (ArXiv)", value=True)

    st.divider()
    st.header("ℹ️ About")
    st.markdown("""
    **Pipeline:**
    - **Planner** → breaks query into tasks
    - **Researcher** → searches sources
    - **Writer** → drafts markdown
    - **Reviewer** → quality check + loop

    **Traced by** LangSmith on every step.
    """)
    st.divider()
    st.caption(f"API: `{API_BASE}`")
    st.caption("[Swagger Docs](http://localhost:8000/docs)")

# ── Main layout ────────────────────────────────────────────────────────────────
tab_query, tab_history = st.tabs(["🔍 New Research", "📜 History"])

with tab_query:
    col_input, col_result = st.columns([1, 2], gap="large")

    with col_input:
        st.subheader("Enter Research Topic")
        query = st.text_area(
            "Research Query",
            placeholder="e.g. Impact of LLMs on software engineering productivity",
            height=120,
            label_visibility="collapsed",
        )

        if st.button("🚀 Start Research", type="primary", use_container_width=True):
            if len(query.strip()) < 5:
                st.warning("Query must be at least 5 characters.")
            else:
                with st.spinner("Submitting job..."):
                    job_id = start_research(query.strip(), depth)
                if job_id:
                    st.session_state.job_id = job_id
                    st.session_state.status = "queued"
                    st.session_state.results = None
                    st.rerun()

        # ── Active / Done job panel ──────────────────────────────────────────────
        if st.session_state.job_id:
            status_data = poll_status(st.session_state.job_id)
            s = status_data.get("status", "")
            p = status_data.get("progress_pct", 0)
            step = status_data.get("current_step", "...")
            url = status_data.get("trace_url")
            err = status_data.get("error")

            st.session_state.status = s
            st.session_state.trace_url = url

            if s == "done":
                # Auto-display report when done — no button needed
                if not st.session_state.results:
                    st.session_state.results = get_report(st.session_state.job_id)

                st.success("✅ Research completed!")
                st.markdown("#### Download")
                md_url = f"{API_BASE}/api/v1/research/{st.session_state.job_id}/report/download"
                pdf_url = f"{API_BASE}/api/v1/research/{st.session_state.job_id}/report/pdf"
                dl1, dl2 = st.columns(2)
                dl1.link_button("📝 Download .md", md_url, use_container_width=True)
                dl2.link_button("📕 Download .pdf", pdf_url, use_container_width=True)

                if st.button("🔄 Refresh Report", use_container_width=True):
                    st.session_state.results = get_report(st.session_state.job_id)
                    st.rerun()

            elif s == "failed":
                st.error(f"❌ Research failed: {err or 'Unknown error'}")
                if st.button("🔄 Try Again"):
                    st.session_state.job_id = None
                    st.session_state.results = None
                    st.session_state.status = None
                    st.rerun()

            elif s:
                # In-progress: show progress bar + keep polling
                render_progress(s, p, step, url)
                if err:
                    st.error(f"Error: {err}")
                time.sleep(3)
                st.rerun()

    # ── Report display ──────────────────────────────────────────────────────────
    with col_result:
        if st.session_state.results:
            report = st.session_state.results
            # Try both field names
            md = (
                report.get("report_markdown")
                or report.get("report_content")
                or ""
            )
            st.subheader(f"📄 Report — `{st.session_state.job_id[:8]}`")
            st.divider()
            if md and len(md) > 10:
                st.markdown(md)
            else:
                st.warning("Report content is empty. Click **Refresh Report** to retry.")
            if report.get("trace_url"):
                st.divider()
                st.caption(f"[View LangSmith Trace]({report['trace_url']})")
        else:
            st.info("👈 Enter a topic and click **Start Research** to begin.")
            with st.expander("💡 Example Research Topics"):
                for ex in [
                    "Impact of LLMs on software engineering productivity",
                    "Recent advances in quantum computing 2025",
                    "Climate change mitigation strategies in Southeast Asia",
                    "Transformer architecture in computer vision",
                    "AI ethics and bias in large language models",
                ]:
                    st.markdown(f"- {ex}")

with tab_history:
    st.subheader("Recent Research Jobs")
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/research", timeout=10.0)
        if resp.status_code == 200:
            jobs = resp.json()
    except Exception:
        st.warning("Cannot reach API. Make sure the server is running at port 8000.")
        jobs = []

    if jobs:
        for job in jobs:
            jid = job.get("job_id", "")
            qry = job.get("query", "")
            sts = job.get("status", "")
            created = (job.get("created_at") or "")[:10]
            badge = (
                '<span class="done-badge">done</span>' if sts == "done"
                else '<span class="fail-badge">failed</span>' if sts == "failed"
                else f'<span style="color:#888">⏳ {sts}</span>'
            )
            st.markdown(
                f"**{qry[:65]}**  {badge}  `{created}`  "
                f"[report]({API_BASE}/api/v1/research/{jid}/report)",
                unsafe_allow_html=True,
            )
    else:
        st.info("No jobs found. Start a research to see history here.")
