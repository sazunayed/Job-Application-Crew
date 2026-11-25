# 4. Customization

## Change the Groq model
Edit `.env`:
```
GROQ_MODEL=groq/llama-3.1-8b-instant      # faster, higher free limits, lower quality
GROQ_MODEL=groq/llama-3.3-70b-versatile   # default, better quality
```
Model names: https://console.groq.com/docs/models

## Change an agent's behaviour
Open `backend/agents.py` and edit `role`, `goal`, `backstory`.

## Change what each output contains
Open `backend/tasks.py` and edit the `description` and `expected_output` of a task.
Examples: add a "Cover Letter" section, request 15 interview questions, ask for a specific resume format.

## Add a 5th agent (e.g. Cover Letter Writer)
1. In `agents.py` create a new `Agent(...)` and add it to the returned dict.
2. In `tasks.py` create a `Task(..., context=[research, resume], output_file=str(OUTPUT_DIR / "cover_letter.md"))` and add it to the returned list.
3. In `crew.py` add `"cover_letter"` to `OUTPUT_FILES`.
4. In `frontend/index.html` add a tab button `data-key="cover_letter"` (and a list item for the agent).

## Adjust token limits
`backend/config.py`: `MAX_JOB_CHARS`, `MAX_GITHUB_CHARS`. In `agents.py`, `max_tokens` controls output length per agent.

## Change the look
Colors are CSS variables at the top of `frontend/style.css`.
