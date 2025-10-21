import json
from pathlib import Path
import streamlit as st

ROADMAP = Path(__file__).resolve().parent / "product" / "roadmap.json"

st.set_page_config(page_title="API Copilot", page_icon="🤖", layout="wide")

st.markdown(
    """
<style>
.feature-card { border:1px solid rgba(0,0,0,0.08); border-radius:14px; padding:12px 14px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,0.04); }
.pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; opacity:.9; border:1px solid rgba(0,0,0,0.08); }
.pill-next { background:#f0f7ff; }
.pill-later { background:#f7f7f7; }
.dot-new { display:inline-block; width:6px; height:6px; background:#5ac8fa; border-radius:999px; margin-right:6px; }
.small { color:#666; font-size:12px; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Agentic API Copilot")
st.caption("Developer assistant with health checks, RAG, and smart routing.")

left, right = st.columns([2.3, 1])

with left:
    st.subheader("Agent Console (placeholder)")
    st.write("⬅️ Your chat/log output would render here. This app focuses on the Coming Soon panel.")

with right:
    with st.expander("Features coming soon", expanded=False):
        data = json.loads(ROADMAP.read_text(encoding="utf-8"))
        st.caption(f"Version {data.get('version')} • Updated {data.get('updated')}")

        st.markdown("#### Next up")
        for item in data.get("next", [])[:6]:
            st.markdown(
                f"""
                <div class="feature-card">
                  <div><span class="dot-new"></span><b>{item['title']}</b> <span class="pill pill-next">Next</span></div>
                  <div class="small">{item['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        later = data.get("later", [])[:4]
        if later:
            st.markdown("#### Later")
            for item in later:
                st.markdown(
                    f"""
                    <div class="feature-card">
                      <div><b>{item['title']}</b> <span class="pill pill-later">Later</span></div>
                      <div class="small">{item['desc']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        if data.get("next"):
            choice = st.radio(
                "Which “Next” item matters most to you?",
                [i["title"] for i in data["next"]],
                index=0,
                horizontal=False,
            )
            if st.button("👍 Register interest (local)"):
                st.success(f"Noted! Interest in: {choice}")

st.divider()
st.caption("Tip: toggle the CLI startup banner with `SHOW_FEATURES=1` in your .env.")

