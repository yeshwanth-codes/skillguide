"""LLM layer (Groq, free tier). Gap analysis is already done by gap_engine.py;
the LLM only personalizes recommendations and writes the roadmap."""
import os
import re
import json
import math
import hashlib
from pathlib import Path

from groq import Groq

MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)

WEEK_DAYS = {1: (1, 7), 2: (8, 14), 3: (15, 21), 4: (22, 30)}

APPROVED_SOURCES = (
    "freeCodeCamp, Kaggle Learn, CS50 (Harvard), official documentation, SQLBolt, "
    "Google ML Crash Course, Hugging Face Course, GeeksforGeeks, MDN Web Docs, "
    "The Odin Project, YouTube (give channel + topic to search)"
)

SYSTEM = (
    "You are an expert career mentor for students. Reply with ONLY valid JSON, "
    "no markdown, no commentary. For 'resource' give a source name from this approved list "
    f"plus a search phrase, never a URL: {APPROVED_SOURCES}."
)


# ---------- helpers ----------
def _clean_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    return json.loads(text[start:end + 1])


def ask_json(user_prompt: str, retries: int = 2) -> dict:
    """Call the LLM, parse JSON, retry on failure, cache results."""
    key = hashlib.sha256((MODEL + user_prompt).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user_prompt}],
                temperature=0.4,
                response_format={"type": "json_object"},
            )
            data = _clean_json(resp.choices[0].message.content)
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as e:  # parse errors, rate limits, network
            last_err = e
    raise RuntimeError(f"LLM failed: {last_err}")


def _fmt_gaps(rows):
    return ", ".join(f"{r['skill']} (have {r['have']}/5, need {r['required']}/5)" for r in rows) or "none"


# ---------- recommendations ----------
def get_recommendations(profile_text: str, analysis: dict) -> dict:
    prompt = f"""Student profile: {profile_text}
Target role: {analysis['role']}. Current readiness: {analysis['score']}%.
Gaps in priority order: {_fmt_gaps(analysis['gaps'])}.

Return JSON:
{{"summary": "3-4 sentence personalised assessment, encouraging but honest",
  "recommendations": [{{"skill": "", "why_it_matters": "", "resource": "", "project_idea": ""}}]}}
Give one recommendation per gap (max 6)."""
    return ask_json(prompt)


# ---------- roadmap (one call per week, so output is never truncated) ----------
def _week_chunks(gaps: list) -> list:
    size = max(1, math.ceil(len(gaps) / 4))
    return [gaps[i * size:(i + 1) * size] for i in range(4)]


def _fallback_week(week: int, skills: list) -> dict:
    a, b = WEEK_DAYS[week]
    names = [s["skill"] for s in skills] or ["Portfolio project"]
    days = []
    for d in range(a, b + 1):
        sk = names[(d - a) % len(names)]
        days.append({"day": d, "focus": f"Learn {sk}",
                     "tasks": [f"Study core concepts of {sk}", f"Practice exercises on {sk}"],
                     "resource": f"freeCodeCamp / official docs: search '{sk} tutorial'",
                     "hours": 2})
    return {"week": week, "goal": f"Build skills in: {', '.join(names)}", "days": days}


def get_week(week: int, skills: list, analysis: dict, profile_text: str, hours: float) -> dict:
    a, b = WEEK_DAYS[week]
    extra = ""
    if week == 4:
        extra = "Last 3 days must be a capstone project that combines all weeks, ending with README + GitHub upload."
    elif week >= 2:
        extra = "End the week with a small mini-project."
    focus = _fmt_gaps(skills) if skills else "revision, portfolio projects and interview preparation"
    prompt = f"""Student: {profile_text}
Target role: {analysis['role']}. Study time: {hours} hours/day.
Week {week} of a 30-day plan, days {a} to {b}. Focus skills this week: {focus}.
{extra}

Return JSON:
{{"week": {week}, "goal": "one sentence",
  "days": [{{"day": {a}, "focus": "", "tasks": ["", ""], "resource": "", "hours": {hours}}}]}}
Include exactly one entry for every day from {a} to {b} ({b - a + 1} entries). 2-3 concrete tasks per day."""
    data = ask_json(prompt)
    days = data.get("days", [])
    if len(days) != b - a + 1:
        raise ValueError("Wrong number of days")
    return data


def generate_plan(profile_text: str, analysis: dict, hours: float = 2.0, progress_cb=None) -> dict:
    """Returns {'summary', 'recommendations', 'weeks', 'used_fallback'}."""
    used_fallback = False
    try:
        rec = get_recommendations(profile_text, analysis)
    except Exception:
        used_fallback = True
        rec = {"summary": f"You are {analysis['score']}% ready for {analysis['role']}. "
                          "Focus on the skills below, starting with the highest priority.",
               "recommendations": [{"skill": r["skill"], "why_it_matters": "Required for this role.",
                                    "resource": "freeCodeCamp / official docs", "project_idea": f"Build a small project using {r['skill']}"}
                                   for r in analysis["gaps"][:6]]}

    weeks = []
    for i, chunk in enumerate(_week_chunks(analysis["gaps"]), start=1):
        if progress_cb:
            progress_cb(i, 4)
        try:
            weeks.append(get_week(i, chunk, analysis, profile_text, hours))
        except Exception:
            used_fallback = True
            weeks.append(_fallback_week(i, chunk))
    return {"summary": rec.get("summary", ""), "recommendations": rec.get("recommendations", []),
            "weeks": weeks, "used_fallback": used_fallback}