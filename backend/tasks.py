from typing import Callable, Optional
from crewai import Task, Agent

REVIEW_MARKER = "---RESUME---"

# Shown in the progress screen, in order. Index 0 (data collection) happens before the crew starts;
# the rest map 1:1 to the tasks returned by build_tasks().
STEP_LABELS = [
    "Fetching job posting and GitHub data",
    "Analyzing the job",
    "Reviewing your profile",
    "Drafting your resume",
    "Fact-checking the resume",
    "Preparing interview material",
    "Writing your cover letter",
    "Checking skill gaps",
]


# File name (without extension) for each task's output, in task order.
TASK_OUTPUT_NAMES = ["job_insights", "candidate_profile", "draft_resume", "fact_check",
                     "interview_materials", "cover_letter", "skill_gaps"]


def build_tasks(
    agents: dict[str, Agent],
    on_task_done: Optional[Callable[[int], None]] = None,
) -> list[Task]:
    """Build the sequential task list. `on_task_done(i)` is called after task i (0-based) finishes.

    Outputs are read from each task's result in crew.py rather than via CrewAI's `output_file`,
    because newer CrewAI versions rewrite absolute output paths and would save files in the wrong place.
    """

    def cb(i: int):
        def _cb(_output):
            if on_task_done:
                on_task_done(i)
        return _cb

    research = Task(
        description=(
            "Analyze this job posting text:\n\n{job_text}\n\n"
            "Produce a Markdown report with sections: Company Overview, Role Summary, "
            "Key Responsibilities, Required Skills, Nice-to-have Skills, Keywords for ATS, "
            "and Culture/Signals."
        ),
        expected_output="A structured Markdown job analysis.",
        agent=agents["researcher"],
        callback=cb(0),
    )
    profile = Task(
        description=(
            "Build a candidate profile from the data below.\n\n"
            "GITHUB DATA:\n{github_data}\n\n"
            "CANDIDATE WRITE-UP:\n{writeup}\n\n"
            "EXISTING RESUME (uploaded by the candidate):\n{resume_text}\n\n"
            "Produce Markdown with sections: Summary, Core Skills, Experience Highlights, "
            "Projects, Strengths, Gaps. Only use facts present in the data. If an existing resume "
            "is provided, carry over its real employers, dates, degrees and achievements exactly."
        ),
        expected_output="A detailed Markdown candidate profile.",
        agent=agents["analyzer"],
        callback=cb(1),
    )
    draft = Task(
        description=(
            "Using the job insights and the candidate profile from the previous tasks, write a "
            "tailored one-page, ATS-friendly resume in Markdown (Summary, Skills, Experience, "
            "Projects, Education). Mirror the job's keywords where truthful. Do NOT fabricate "
            "employers, degrees or metrics; use placeholders like [Add metric] if needed."
        ),
        expected_output="A complete tailored resume in Markdown.",
        agent=agents["strategist"],
        context=[research, profile],
        callback=cb(2),
    )
    review = Task(
        description=(
            "Audit the DRAFT RESUME from the previous task for anything that is not supported by the "
            "candidate's own data. SOURCES OF TRUTH: the candidate profile (previous task), plus:\n\n"
            "EXISTING RESUME (uploaded by the candidate):\n{resume_text}\n\n"
            "CANDIDATE WRITE-UP:\n{writeup}\n\n"
            "Check every employer, job title, date, degree, certification, metric, tool, skill and "
            "project in the draft. A skill the job asks for but the candidate does not show must NOT "
            "appear as a skill or as experience. Anything unsupported must be removed, reworded to "
            "what the sources actually say, or replaced with a placeholder such as [Add metric]. "
            "Keep everything that is supported; do not shorten the resume for its own sake.\n\n"
            "Reply in EXACTLY this layout, with no code fences:\n"
            "Line 1: VERDICT: PASS (nothing needed changing) or VERDICT: CORRECTED\n"
            "Then a section '## Fact-check report' with one bullet per problem in the form "
            "'- **<claim>**: <why it is unsupported> -> <what you changed>'. "
            "If there were none write '- No unsupported claims found.'\n"
            f"Then a line containing exactly {REVIEW_MARKER}\n"
            "Then the complete final resume in Markdown, with every fix applied."
        ),
        expected_output=(
            f"A VERDICT line, a '## Fact-check report' section, the line {REVIEW_MARKER}, "
            "then the full corrected resume in Markdown."
        ),
        agent=agents["fact_checker"],
        context=[profile, draft],
        callback=cb(3),
    )
    interview = Task(
        description=(
            "Using the job insights and the fact-checked resume (it follows the "
            f"{REVIEW_MARKER} line in the previous task's answer), create interview prep in Markdown: "
            "10 likely technical questions with answer outlines, 5 behavioural questions with "
            "STAR talking points, 5 smart questions to ask the interviewer, and a short "
            "'Tell me about yourself' script. Base every answer only on experience in the resume."
        ),
        expected_output="Markdown interview materials.",
        agent=agents["preparer"],
        context=[research, review],
        callback=cb(4),
    )
    cover = Task(
        description=(
            "Write a cover letter in Markdown for this job, using the job insights and the "
            f"fact-checked resume (it follows the {REVIEW_MARKER} line in the fact-check answer) and "
            "the candidate profile. Rules: 250-350 words; address it to 'Dear Hiring Manager,' unless "
            "a name appears in the job text; open with something specific about the role or company, "
            "not 'I am writing to apply'; use 2-3 concrete examples that really appear in the resume; "
            "connect them to the job's main requirements; close with a short call to action; sign off "
            "with the candidate's name if known, otherwise [Your Name]. Never invent employers, "
            "achievements or numbers, and do not claim skills the candidate lacks. Output only the letter."
        ),
        expected_output="A complete cover letter in Markdown, 250-350 words.",
        agent=agents["cover_writer"],
        context=[research, profile, review],
        callback=cb(5),
    )
    gaps = Task(
        description=(
            "Compare the job insights with the candidate profile. List the skills, tools, "
            "frameworks or libraries that the job requires (or strongly prefers) but the "
            "candidate does NOT clearly have. The very first line of your answer must be exactly: "
            "MATCH_SCORE: followed by a number from 0 to 100 estimating how well the candidate "
            "matches the job. After that line return ONLY a JSON array (no markdown fences, "
            "no commentary) with at most 8 items. Each item must have exactly these keys: "
            "skill (short name such as 'Docker' or 'PostgreSQL'), priority (one of "
            "'high', 'medium', 'low'), why (one short sentence on why it matters for this job)."
        ),
        expected_output="A MATCH_SCORE line followed by a JSON array of missing skills.",
        agent=agents["skill_advisor"],
        context=[research, profile],
        callback=cb(6),
    )
    return [research, profile, draft, review, interview, cover, gaps]
