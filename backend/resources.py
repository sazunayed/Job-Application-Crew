"""Builds reliable learning links for a skill.

LLMs often invent URLs, so we never ask the model for links. Instead we use
(1) a curated map of official documentation and (2) search URLs that always work.
"""
import json
import re
from urllib.parse import quote_plus

OFFICIAL_DOCS = {
    "python": "https://docs.python.org/3/tutorial/",
    "javascript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    "typescript": "https://www.typescriptlang.org/docs/",
    "react": "https://react.dev/learn",
    "node.js": "https://nodejs.org/en/learn",
    "nodejs": "https://nodejs.org/en/learn",
    "docker": "https://docs.docker.com/get-started/",
    "kubernetes": "https://kubernetes.io/docs/tutorials/",
    "git": "https://git-scm.com/doc",
    "sql": "https://www.postgresql.org/docs/current/tutorial.html",
    "postgresql": "https://www.postgresql.org/docs/current/tutorial.html",
    "mongodb": "https://www.mongodb.com/docs/manual/tutorial/",
    "redis": "https://redis.io/docs/latest/",
    "fastapi": "https://fastapi.tiangolo.com/tutorial/",
    "django": "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
    "flask": "https://flask.palletsprojects.com/en/stable/tutorial/",
    "aws": "https://docs.aws.amazon.com/getting-started/",
    "azure": "https://learn.microsoft.com/en-us/azure/",
    "gcp": "https://cloud.google.com/docs",
    "terraform": "https://developer.hashicorp.com/terraform/tutorials",
    "pytorch": "https://pytorch.org/tutorials/",
    "tensorflow": "https://www.tensorflow.org/tutorials",
    "scikit-learn": "https://scikit-learn.org/stable/user_guide.html",
    "pandas": "https://pandas.pydata.org/docs/getting_started/index.html",
    "numpy": "https://numpy.org/doc/stable/user/absolute_beginners.html",
    "langchain": "https://python.langchain.com/docs/introduction/",
    "crewai": "https://docs.crewai.com/",
    "graphql": "https://graphql.org/learn/",
    "java": "https://dev.java/learn/",
    "spring boot": "https://spring.io/guides",
    "go": "https://go.dev/doc/tutorial/",
    "rust": "https://doc.rust-lang.org/book/",
    "linux": "https://linuxjourney.com/",
    "ci/cd": "https://docs.github.com/en/actions",
    "github actions": "https://docs.github.com/en/actions",
    "html": "https://developer.mozilla.org/en-US/docs/Learn/HTML",
    "css": "https://developer.mozilla.org/en-US/docs/Learn/CSS",
    "tailwind": "https://tailwindcss.com/docs",
    "next.js": "https://nextjs.org/learn",
    "vue": "https://vuejs.org/guide/introduction.html",
    "angular": "https://angular.dev/tutorials",
}


def links_for(skill: str) -> list[dict]:
    q = quote_plus(skill)
    links = []
    official = OFFICIAL_DOCS.get(skill.strip().lower())
    if official:
        links.append({"label": "Official docs", "url": official})
    else:
        links.append({"label": "Official docs (search)", "url": f"https://duckduckgo.com/?q={quote_plus(skill + ' official documentation')}"})
    links += [
        {"label": "YouTube tutorials", "url": f"https://www.youtube.com/results?search_query={quote_plus(skill + ' tutorial for beginners')}"},
        {"label": "freeCodeCamp", "url": f"https://www.freecodecamp.org/news/search/?query={q}"},
        {"label": "Coursera courses", "url": f"https://www.coursera.org/search?query={q}"},
        {"label": "GitHub examples", "url": f"https://github.com/search?q={q}&type=repositories&s=stars&o=desc"},
    ]
    return links


def parse_skill_gaps(raw: str) -> list[dict]:
    """Parse the agent's JSON output defensively and attach learning links."""
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items[:8]:
        if not isinstance(it, dict) or not it.get("skill"):
            continue
        skill = str(it["skill"]).strip()
        priority = str(it.get("priority", "medium")).lower()
        out.append({
            "skill": skill,
            "priority": priority if priority in ("high", "medium", "low") else "medium",
            "why": str(it.get("why", "")).strip(),
            "links": links_for(skill),
        })
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda x: order[x["priority"]])


def parse_match_score(raw: str):
    m = re.search(r"MATCH_SCORE:\s*(\d{1,3})", raw or "")
    return max(0, min(100, int(m.group(1)))) if m else None
