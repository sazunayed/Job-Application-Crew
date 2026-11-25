"""Data collection helpers: job posting page + GitHub profile."""
import re
import requests
from bs4 import BeautifulSoup
from .config import GITHUB_TOKEN, MAX_JOB_CHARS, MAX_GITHUB_CHARS

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobCrewBot/1.0)"}


def scrape_job_posting(url: str) -> str:
    """Download a job posting page and return cleaned text."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return f"[Could not fetch job URL: {e}]"
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:MAX_JOB_CHARS] or "[Job page had no readable text]"


def _github_username(url: str) -> str:
    m = re.search(r"github\.com/([A-Za-z0-9-]+)", url)
    return m.group(1) if m else url.strip().strip("/")


def fetch_github_profile(url: str) -> str:
    """Use the public GitHub API to summarise a user's profile and top repos."""
    user = _github_username(url)
    headers = {"Accept": "application/vnd.github+json", **HEADERS}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        u = requests.get(f"https://api.github.com/users/{user}", headers=headers, timeout=20)
        u.raise_for_status()
        u = u.json()
        repos = requests.get(
            f"https://api.github.com/users/{user}/repos",
            params={"sort": "updated", "per_page": 30},
            headers=headers, timeout=20,
        ).json()
    except Exception as e:
        return f"[Could not fetch GitHub profile '{user}': {e}]"

    own = [r for r in repos if isinstance(r, dict) and not r.get("fork")]
    own.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)

    langs: dict[str, int] = {}
    for r in own:
        if r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1

    lines = [
        f"Name: {u.get('name') or user}",
        f"Bio: {u.get('bio') or 'n/a'}",
        f"Location: {u.get('location') or 'n/a'}",
        f"Public repos: {u.get('public_repos')} | Followers: {u.get('followers')}",
        "Top languages: " + ", ".join(f"{k} ({v})" for k, v in sorted(langs.items(), key=lambda x: -x[1])[:6]),
        "",
        "Notable repositories:",
    ]
    for r in own[:8]:
        lines.append(
            f"- {r['name']} [{r.get('language') or 'n/a'}] stars {r.get('stargazers_count', 0)}: "
            f"{r.get('description') or 'no description'} (topics: {', '.join(r.get('topics', [])) or 'none'})"
        )
    return "\n".join(lines)[:MAX_GITHUB_CHARS]
