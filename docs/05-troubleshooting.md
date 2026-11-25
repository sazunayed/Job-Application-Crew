# 5. Troubleshooting & FAQ

| Problem | Cause | Fix |
|---------|-------|-----|
| `GROQ_API_KEY is missing` | `.env` not created/filled | Copy `.env.example` to `.env`, add key, restart |
| `RateLimitError` / 429 from Groq | Free-tier limits | Wait 1 minute, retry, or use `groq/llama-3.1-8b-instant` |
| `Request too large` / token error | Inputs too long | Shorten write-up, lower `MAX_JOB_CHARS` |
| Job insights say "Could not fetch job URL" | Site blocks bots / needs login | Use a company careers page, or paste the description into your write-up |
| GitHub data says "Could not fetch" | Wrong username or API rate limit | Check URL; set `GITHUB_TOKEN` in `.env` |
| `ModuleNotFoundError` | venv not active / deps missing | Activate venv, run `pip install -r requirements.txt` |
| CrewAI install fails | Unsupported Python version | Use Python 3.10 – 3.13 |
| Page loads but nothing happens | Backend error | Check the terminal running `python run.py` for the log |
| Tabs show raw text, not formatted | CDN for `marked` blocked offline | Connect to internet; raw markdown is still usable |
| Port 8000 already in use | Another app running | Change `port=8000` in `run.py` |
| Empty or short output | Model returned little | Re-run; use the 70b model; give a richer write-up |

## FAQ
**Does it send my data anywhere?** Your inputs go to Groq (LLM provider), GitHub's public API, and the job site you provide. Nothing else. Do not include passwords, ID numbers, or sensitive data in the write-up.

**Is the resume guaranteed ATS-safe?** It uses simple headings and plain text, which ATS systems parse well, but you must review and export it cleanly.

**Can the AI make mistakes?** Yes. Always verify facts, dates and claims before applying.

**Can I run it offline?** No, it needs Groq and (optionally) GitHub/job sites.

**Where are the generated files saved?** `backend/outputs/<run id>/`, one folder per run (the newest 10 are kept). The in-app download buttons are the easiest way to get them.

**The progress screen stops or the result never arrives.** The run was probably cut off by a Groq rate limit or a network drop. Wait a minute and retry, or switch to a smaller model (`GROQ_MODEL`). If you run behind a proxy, make sure it does not buffer `text/event-stream` responses.

**The Fact check badge says "Not applied".** The model did not follow the `VERDICT / report / ---RESUME---` layout, or its answer was cut off. You get the unreviewed draft. Retry, or try a larger model. Raising `max_tokens` in `agents.py` can also help.

**PDF/Word download fails.** Run `pip install -r requirements.txt` again (adds `reportlab`).

**`RateLimitError ... output tokens per minute (OTPM)`.** Your model's free-tier limit is too small for this pipeline (some models allow only 1,000 output tokens/min). The app retries automatically (`LLM_RETRIES`), but the run will be slow or still fail on tiny limits. Best fix: use `GROQ_MODEL=groq/llama-3.3-70b-versatile` (or `groq/llama-3.1-8b-instant`), or upgrade your Groq tier. Check each model's limits at https://console.groq.com/docs/rate-limits.

**"Could not read the job posting from that link".** The page is built with JavaScript or blocks bots, so the app got no text. Paste the job description into the **Job description** box instead. The run now stops early in this case instead of building a resume from nothing.

**`RateLimitError ... tokens per minute (TPM)`.** Add `LLM_COOLDOWN_SECONDS=20` and `LLM_MAX_TOKENS=2000` to `.env`. The cooldown lets the per-minute token window recover between agents.

**Using OpenRouter.** Set `OPENROUTER_API_KEY` and `LLM_MODEL=openrouter/<model-id>:free` in `.env` (for Gemma 4: `LLM_MODEL=openrouter/google/gemma-4-26b-a4b-it:free`). The `openrouter/` prefix is required; the model id from the OpenRouter page goes after it. Free models allow 20 requests/min and 50/day (1,000/day after buying at least 10 credits); one run uses about 7 requests. Free model availability changes, so copy the id from https://openrouter.ai/models?q=free. The `GROQ_MODEL` name is kept for backwards compatibility; it accepts any provider prefix.
