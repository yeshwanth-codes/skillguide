import os
import html
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)
try:  # Streamlit Cloud secrets
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

from gap_engine import ROLES, LEVELS, KNOWN_SKILLS, build_profile, analyze, best_roles  # noqa: E402
from llm import generate_plan  # noqa: E402

st.set_page_config(page_title="SkillBridge", page_icon="🎯", layout="wide")

BLUE, GREEN, AMBER, CORAL = "#1F4FD8", "#1E9E6A", "#D9930D", "#D64545"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, [class*="st-"] {{ font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }}
.block-container {{ padding-top: 2.2rem; max-width: 1150px; }}
#MainMenu, footer {{ visibility: hidden; }}

.hero h1 {{ font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; margin: 0 0 .25rem 0; padding: 0; }}
.hero p {{ font-size: 1.08rem; color: #55607A; margin: 0 0 1.1rem 0; max-width: 40rem; }}

.stepper {{ display: flex; gap: .6rem; flex-wrap: wrap; margin-bottom: 1.6rem; }}
.step {{ padding: .35rem .85rem; border-radius: 999px; font-size: .85rem; font-weight: 600;
        background: #E7EBF3; color: #6B7490; }}
.step.done {{ background: #DDF3E9; color: #17724D; }}
.step.now {{ background: {BLUE}; color: #fff; }}

.card {{ background: #fff; border: 1px solid #E3E7F0; border-radius: 14px; padding: 1.1rem 1.3rem; margin-bottom: 1rem; }}
.callout {{ background: #EEF3FF; border-left: 4px solid {BLUE}; border-radius: 8px; padding: .9rem 1.1rem; margin: .6rem 0 1rem 0; }}
.callout b {{ color: {BLUE}; }}

.row {{ display: grid; grid-template-columns: 1.6fr 2fr .5fr 1fr; align-items: center; gap: .8rem;
       padding: .55rem 0; border-bottom: 1px solid #EEF0F6; }}
.row:last-child {{ border-bottom: none; }}
.rname {{ font-weight: 600; }}
.tier {{ display: block; font-size: .72rem; font-weight: 500; color: #7B849C; }}
.track {{ height: 8px; background: #E7EBF3; border-radius: 6px; overflow: hidden; }}
.fill {{ height: 100%; border-radius: 6px; }}
.fill.ok {{ background: {GREEN}; }} .fill.part {{ background: {AMBER}; }} .fill.miss {{ background: {CORAL}; }}
.rlvl {{ font-size: .85rem; color: #55607A; text-align: right; }}
.chip {{ display: inline-block; padding: .15rem .65rem; border-radius: 999px; font-size: .78rem; font-weight: 600; text-align: center; }}
.chip-ok {{ background: #DDF3E9; color: #17724D; }}
.chip-part {{ background: #FCEFD2; color: #8A5A00; }}
.chip-miss {{ background: #FBE0E0; color: #A22E2E; }}
@media (max-width: 700px) {{ .row {{ grid-template-columns: 1fr 1fr; }} }}

[data-testid="stMetric"] {{ background: #fff; border: 1px solid #E3E7F0; border-radius: 14px; padding: .9rem 1.1rem; }}
[data-testid="stSidebar"] {{ border-right: 1px solid #E3E7F0; }}
button[kind="primary"] {{ font-weight: 700; border-radius: 10px; }}
</style>
""", unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


# ---------------- session defaults (so widgets never need a `value=` argument) ----------------
ss = st.session_state
ss.setdefault("name", "")
ss.setdefault("skills_sel", [])
ss.setdefault("custom", "")
ss.setdefault("custom_level", "Intermediate")
ss.setdefault("exp", "")
ss.setdefault("interests", "")
ss.setdefault("hours", 2.0)
ss.setdefault("role_sel", list(ROLES)[0])


def load_sample():
    ss.name = "Asha"
    ss.skills_sel = ["Python", "SQL", "Pandas"]
    ss["lvl_Python"], ss["lvl_SQL"], ss["lvl_Pandas"] = "Intermediate", "Beginner", "Beginner"
    ss.exp = "Built a bill generator app in Python. One college data project."
    ss.interests = "Data, cloud"
    ss.role_sel = "Data Analyst"


# ---------------- sidebar: profile + role ----------------
with st.sidebar:
    st.markdown("### Your profile")
    st.button("Try a sample student", on_click=load_sample, width="stretch")
    st.text_input("Name", key="name", placeholder="Your name")
    st.multiselect("Skills you already have", KNOWN_SKILLS, key="skills_sel",
                   placeholder="Search and pick skills")
    raw = {}
    for s in ss.skills_sel:
        ss.setdefault(f"lvl_{s}", "Beginner")
        raw[s] = LEVELS[st.select_slider(s, list(LEVELS), key=f"lvl_{s}")]
    with st.expander("Add skills that aren't in the list"):
        st.text_input("Skill names, separated by commas", key="custom", placeholder="e.g. ML, JS, Power BI")
        st.selectbox("Your level in these", list(LEVELS), key="custom_level")
        for c in [x for x in ss.custom.split(",") if x.strip()]:
            raw[c] = LEVELS[ss.custom_level]
    st.text_area("Projects and internships", key="exp", placeholder="e.g. Built a bill generator in Python")
    st.text_input("Interests", key="interests", placeholder="e.g. AI, finance, cloud")
    st.slider("Study hours per day", 1.0, 8.0, step=0.5, key="hours")

    st.markdown("### Target role")
    st.selectbox("Role", list(ROLES), key="role_sel", label_visibility="collapsed")
    st.caption(ROLES[ss.role_sel]["description"])
    go_clicked = st.button("Analyze my skills", type="primary", width="stretch")

if go_clicked:
    if not raw:
        st.sidebar.error("Pick at least one skill so we have something to compare.")
    else:
        profile = build_profile(raw)
        ss.profile = profile
        ss.analysis = analyze(profile, ss.role_sel)
        ss.profile_text = (
            f"Name: {ss.name or 'Student'}. Skills: {', '.join(f'{k} (level {v}/5)' for k, v in profile.items())}. "
            f"Experience: {ss.exp or 'none'}. Interests: {ss.interests or 'none'}."
        )
        ss.pop("plan", None)

# ---------------- header + stepper ----------------
has_analysis = "analysis" in ss
has_plan = bool(ss.get("plan"))
steps = [("Add your skills", "done" if has_analysis else "now"),
         ("See your gaps", "done" if has_analysis else ""),
         ("Get your 30-day plan", "done" if has_plan else ("now" if has_analysis else ""))]
st.markdown(
    '<div class="hero"><h1>SkillBridge</h1>'
    "<p>Choose a job role, see exactly which skills you're missing, and get a 30-day plan to close the gap.</p></div>"
    '<div class="stepper">' + "".join(f'<span class="step {c}">{"✓ " if c == "done" else ""}{t}</span>' for t, c in steps)
    + "</div>", unsafe_allow_html=True)

if not has_analysis:
    st.markdown(
        '<div class="card"><b>Start in the sidebar.</b><br>Pick the skills you have, choose a role and press '
        '<b>Analyze my skills</b>. No time to type? Press <b>Try a sample student</b> first.</div>',
        unsafe_allow_html=True)
    st.stop()

a = ss.analysis


# ---------------- helpers ----------------
def skill_row(r):
    cls = {"matched": "ok", "partial": "part", "missing": "miss"}[r["status"]]
    label = {"matched": "Ready", "partial": "Needs work", "missing": "Not started"}[r["status"]]
    tier = "Must-have" if r["tier"] == "must" else "Nice-to-have"
    pct = max(int(r["credit"] * 100), 3)
    return (f'<div class="row"><div class="rname">{esc(r["skill"])}<span class="tier">{tier}</span></div>'
            f'<div class="track"><div class="fill {cls}" style="width:{pct}%"></div></div>'
            f'<div class="rlvl">{r["have"]}/{r["required"]}</div><span class="chip chip-{cls}">{label}</span></div>')


def gauge(score, projected):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number={"suffix": "%", "font": {"size": 46}},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": BLUE, "thickness": 0.7},
               "bgcolor": "#E7EBF3", "borderwidth": 0,
               "threshold": {"line": {"color": GREEN, "width": 4}, "thickness": 0.9, "value": projected}}))
    fig.update_layout(height=230, margin=dict(t=20, b=0, l=25, r=25), paper_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#14213D"})
    return fig


def plan_markdown(plan):
    out = [f"# 30-day roadmap: {a['role']}", "", plan.get("summary", ""), ""]
    for w in plan["weeks"]:
        out += [f"## Week {w['week']}: {w.get('goal', '')}", ""]
        for d in w["days"]:
            out.append(f"### Day {d['day']}: {d.get('focus', '')} ({d.get('hours', '')}h)")
            out += [f"- [ ] {t}" for t in d["tasks"]]
            out += [f"- Resource: {d.get('resource', '')}", ""]
    return "\n".join(out)


tab_overview, tab_gaps, tab_plan = st.tabs(["Overview", "Skill gaps", "30-day plan"])

# ---------------- overview ----------------
with tab_overview:
    verdict = ("Early stage: a clear plan will help a lot." if a["score"] < 40 else
               "Making progress: a few focused gaps remain." if a["score"] < 70 else
               "Nearly job-ready: polish the last gaps.")
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        st.markdown(f"**Readiness for {esc(a['role'])}**")
        st.plotly_chart(gauge(a["score"], a["projected"]), width="stretch")
        st.caption(f"{verdict} The green marker shows where you'd be ({a['projected']}%) after closing the must-have gaps.")
    with right:
        c1, c2, c3 = st.columns(3)
        c1.metric("Ready", len(a["matched"]))
        c2.metric("Needs work", len(a["partial"]))
        c3.metric("Not started", len(a["missing"]))
        top = [r["skill"] for r in a["gaps"][:3]]
        if top:
            st.markdown(f'<div class="callout"><b>Learn these first:</b> {esc(", ".join(top))}. '
                        "They carry the most weight for this role.</div>", unsafe_allow_html=True)
        else:
            st.success("You meet every requirement for this role.")
        with st.expander("Which role fits you best?"):
            for role, sc in best_roles(ss.profile):
                st.markdown(f"**{esc(role)}** · {sc}%")
                st.progress(sc / 100)

# ---------------- skill gaps ----------------
with tab_gaps:
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown('<div class="card">' + "".join(skill_row(r) for r in a["rows"]) + "</div>", unsafe_allow_html=True)
        st.caption("Numbers show your level out of the level this role expects (1 = beginner, 5 = advanced).")
    with right:
        cats = [r["skill"] for r in a["rows"]]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=[r["required"] for r in a["rows"]], theta=cats, fill="toself",
                                      name="Role needs", line_color=AMBER))
        fig.add_trace(go.Scatterpolar(r=[r["have"] for r in a["rows"]], theta=cats, fill="toself",
                                      name="You have", line_color=BLUE))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5], showticklabels=False)), height=400,
                          margin=dict(t=30, b=30, l=40, r=40), paper_bgcolor="rgba(0,0,0,0)",
                          legend=dict(orientation="h", y=-0.08))
        st.plotly_chart(fig, width="stretch")

# ---------------- 30-day plan ----------------
with tab_plan:
    plan = ss.get("plan")
    if not plan:
        st.markdown("#### Turn these gaps into a plan")
        st.write("We'll write personalised recommendations and a week-by-week schedule based on your "
                 f"{ss.hours:g} study hours a day.")
        if not os.getenv("GROQ_API_KEY"):
            st.caption("No Groq API key found, so you'll get the offline plan. Add GROQ_API_KEY to your .env file for AI-written plans.")
        if st.button("Build my 30-day plan", type="primary"):
            bar = st.progress(0, text="Starting...")
            try:
                ss.plan = generate_plan(ss.profile_text, a, ss.hours,
                                        lambda i, n: bar.progress(i / n, text=f"Writing week {i} of {n}..."))
            except Exception as e:
                st.error(f"Couldn't build the plan: {e}. Check your API key and internet connection, then try again.")
            bar.empty()
            if ss.get("plan"):
                st.rerun()
    else:
        if plan["used_fallback"]:
            st.info("Part of this plan uses the offline template because the AI service didn't respond. "
                    "Check your API key and rebuild for the full version.")

        task_keys = [f"t_{w['week']}_{d['day']}_{i}" for w in plan["weeks"] for d in w["days"] for i in range(len(d["tasks"]))]
        done = sum(bool(ss.get(k)) for k in task_keys)
        top_l, top_r = st.columns([3, 1])
        with top_l:
            st.markdown(f"**{done} of {len(task_keys)} tasks done**")
            st.progress(done / max(len(task_keys), 1))
        with top_r:
            st.download_button("Download plan", plan_markdown(plan), file_name="my_30_day_plan.md",
                               mime="text/markdown", width="stretch")
            if st.button("Rebuild plan", width="stretch"):
                ss.pop("plan", None)
                st.rerun()

        if plan.get("summary"):
            st.markdown(f'<div class="callout">{esc(plan["summary"])}</div>', unsafe_allow_html=True)

        with st.expander("What to learn and why", expanded=False):
            for rec in plan["recommendations"]:
                st.markdown(f"**{esc(rec.get('skill', ''))}**")
                st.write(rec.get("why_it_matters", ""))
                st.caption(f"Learn from: {rec.get('resource', '')}  |  Project: {rec.get('project_idea', '')}")

        tabs = st.tabs([f"Week {w['week']}" for w in plan["weeks"]])
        for tab, w in zip(tabs, plan["weeks"]):
            with tab:
                wk = [f"t_{w['week']}_{d['day']}_{i}" for d in w["days"] for i in range(len(d["tasks"]))]
                wdone = sum(bool(ss.get(k)) for k in wk)
                st.markdown(f"**{esc(w.get('goal', ''))}**")
                st.caption(f"{wdone} of {len(wk)} tasks done this week")
                for d in w["days"]:
                    with st.container(border=True):
                        st.markdown(f"**Day {d['day']}: {esc(d.get('focus', ''))}** &nbsp; `{d.get('hours', '')} h`")
                        for i, t in enumerate(d["tasks"]):
                            st.checkbox(t, key=f"t_{w['week']}_{d['day']}_{i}")
                        st.caption(f"Learn from: {d.get('resource', '')}")