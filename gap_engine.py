"""Deterministic skill-gap analysis. No LLM here, so results are consistent and explainable."""
import json
from pathlib import Path

ROLES = json.loads((Path(__file__).parent / "roles.json").read_text(encoding="utf-8"))

# Proficiency scale: 1-5 (role requirements use the same scale)
LEVELS = {"Beginner": 1, "Intermediate": 3, "Advanced": 5}

# Every canonical skill name used in roles.json
KNOWN_SKILLS = sorted({s["name"] for r in ROLES.values() for s in r["skills"]} | {
    "Scikit-learn", "TensorFlow", "PyTorch", "Matplotlib", "Power BI", "Tableau",
    "Flask", "Django", "FastAPI", "MySQL", "PostgreSQL", "MongoDB", "Java", "C++",
})

# Alias map: whatever the student types -> canonical name
ALIASES = {
    "js": "JavaScript", "javascript": "JavaScript", "py": "Python", "python3": "Python",
    "ml": "Machine Learning", "dl": "Deep Learning", "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn", "powerbi": "Power BI", "power-bi": "Power BI",
    "html": "HTML/CSS", "css": "HTML/CSS", "html5": "HTML/CSS", "reactjs": "React",
    "react.js": "React", "numpy": "NumPy", "pandas": "Pandas", "oops": "OOP",
    "dsa": "Data Structures", "data structure": "Data Structures", "rest api": "APIs",
    "api": "APIs", "rest": "APIs", "ms excel": "Excel", "excel": "Excel",
    "stats": "Statistics", "viz": "Data Visualization", "visualization": "Data Visualization",
    "llm": "LLMs", "genai": "LLMs", "prompt engineering": "LLMs", "openai": "LLMs",
    "aws": "Cloud", "azure": "Cloud", "gcp": "Cloud", "unit testing": "Testing", "pytest": "Testing",
    "github": "Git", "sql": "SQL",
}

# Owning a specific tool counts toward broader skills in roles
IMPLIES = {
    "Scikit-learn": ["Machine Learning"],
    "TensorFlow": ["Deep Learning", "Machine Learning"],
    "PyTorch": ["Deep Learning", "Machine Learning"],
    "Matplotlib": ["Data Visualization"],
    "Power BI": ["Data Visualization"],
    "Tableau": ["Data Visualization"],
    "Flask": ["Web Frameworks", "APIs"],
    "Django": ["Web Frameworks"],
    "FastAPI": ["Web Frameworks", "APIs"],
    "MySQL": ["SQL", "Databases"],
    "PostgreSQL": ["SQL", "Databases"],
    "MongoDB": ["Databases"],
    "SQL": ["Databases"],
}

_CANON = {s.lower(): s for s in KNOWN_SKILLS}


def normalize(skill: str) -> str:
    key = skill.strip().lower()
    return ALIASES.get(key) or _CANON.get(key) or skill.strip().title()


def build_profile(raw: dict) -> dict:
    """raw: {typed skill: level 1-5}  ->  {canonical skill: level}, including implied skills."""
    prof = {}
    for skill, lvl in raw.items():
        name = normalize(skill)
        prof[name] = max(prof.get(name, 0), lvl)
    for skill, lvl in list(prof.items()):
        for implied in IMPLIES.get(skill, []):
            prof[implied] = max(prof.get(implied, 0), lvl)
    return prof


def analyze(profile: dict, role: str) -> dict:
    skills = ROLES[role]["skills"]
    total_w = sum(s["weight"] for s in skills)
    rows, earned, earned_if_must_fixed = [], 0.0, 0.0

    for s in skills:
        have = profile.get(s["name"], 0)
        credit = min(have / s["level"], 1.0)
        status = "matched" if credit >= 1 else ("partial" if credit > 0 else "missing")
        tier_factor = 1.0 if s["tier"] == "must" else 0.6
        rows.append({
            "skill": s["name"], "tier": s["tier"], "weight": s["weight"],
            "required": s["level"], "have": have, "credit": round(credit, 2),
            "status": status,
            "priority": round(s["weight"] * (1 - credit) * tier_factor, 2),
        })
        earned += s["weight"] * credit
        earned_if_must_fixed += s["weight"] * (1.0 if s["tier"] == "must" else credit)

    gaps = sorted([r for r in rows if r["status"] != "matched"], key=lambda r: -r["priority"])
    return {
        "role": role,
        "score": round(100 * earned / total_w),
        "projected": round(100 * earned_if_must_fixed / total_w),
        "rows": rows,
        "matched": [r for r in rows if r["status"] == "matched"],
        "partial": [r for r in rows if r["status"] == "partial"],
        "missing": [r for r in rows if r["status"] == "missing"],
        "gaps": gaps,
    }


def best_roles(profile: dict) -> list:
    """Multi-role comparison: which role fits the student best?"""
    return sorted(((r, analyze(profile, r)["score"]) for r in ROLES), key=lambda x: -x[1])