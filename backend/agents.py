import litellm
from crewai import Agent, LLM
from .config import API_KEY, GROQ_MODEL, LLM_MAX_TOKENS, LLM_RETRIES, IS_OPENROUTER

# Silently drop request parameters a provider does not support instead of failing the call.
litellm.drop_params = True


def build_llm(temperature: float = 0.4) -> LLM:
    # max_tokens is higher than before because the fact checker returns a report AND the full resume.
    kwargs = dict(model=GROQ_MODEL, api_key=API_KEY, temperature=temperature, max_tokens=LLM_MAX_TOKENS)
    if IS_OPENROUTER:
        # Newer CrewAI sends openrouter/... models through the OpenAI client, which rejects
        # LiteLLM's `num_retries`. `max_retries` is accepted by both code paths.
        kwargs["max_retries"] = LLM_RETRIES
    else:
        kwargs["num_retries"] = LLM_RETRIES
    return LLM(**kwargs)


def build_agents(llm: LLM) -> dict[str, Agent]:
    # OpenRouter models are unknown to CrewAI, which then assumes a tiny 8K context window and
    # auto-summarises the earlier tasks. Gemma 4 really has 262K, so turn that off there.
    ctx = {"respect_context_window": False} if IS_OPENROUTER else {}
    common = dict(llm=llm, verbose=True, allow_delegation=False, **ctx)

    job_researcher = Agent(
        role="Job Researcher",
        goal="Extract everything a candidate needs to know about the role, company, skills and responsibilities.",
        backstory="A senior tech recruiter who dissects job postings and knows what hiring managers truly value.",
        **common,
    )
    profile_analyzer = Agent(
        role="Profile Analyzer",
        goal="Build a detailed, honest professional profile from the candidate's GitHub data and write-up.",
        backstory="A technical career coach who turns raw repos and notes into a clear skills and impact narrative.",
        **common,
    )
    resume_strategist = Agent(
        role="Resume Strategist",
        goal="Write a tailored, ATS-friendly resume in Markdown that maps the candidate's real experience to the job requirements.",
        backstory="An ATS expert and resume writer. You never invent facts; you only reframe what the candidate actually has.",
        **common,
    )
    interview_preparer = Agent(
        role="Interview Preparer",
        goal="Prepare likely interview questions and strong talking points based on the job and the tailored resume.",
        backstory="A veteran interviewer who has run hundreds of technical and behavioural interviews.",
        **common,
    )
    skill_advisor = Agent(
        role="Skill Gap Advisor",
        goal="Compare the job requirements with the candidate profile and list the skills, tools or libraries the candidate is missing.",
        backstory="A career mentor who spots skill gaps precisely and ranks them by how much they matter for getting hired.",
        **common,
    )
    fact_checker = Agent(
        role="Fact-Check Reviewer",
        goal="Audit the draft resume line by line against the candidate's real data, remove or fix anything unsupported, and return a corrected resume.",
        backstory="A meticulous background-check specialist. You assume nothing: every employer, title, date, degree, metric, tool and project in a resume must be traceable to the candidate's own data, otherwise it is removed or replaced with a placeholder.",
        llm=build_llm(0.1), verbose=True, allow_delegation=False, **ctx,
    )
    cover_writer = Agent(
        role="Cover Letter Writer",
        goal="Write a concise, specific and honest cover letter that connects the candidate's verified experience to this company and role.",
        backstory="A career writer who avoids clichés and buzzwords. You open with something concrete, back every claim with a real example from the candidate's resume, and never invent facts.",
        **common,
    )
    return {
        "skill_advisor": skill_advisor,
        "researcher": job_researcher,
        "analyzer": profile_analyzer,
        "strategist": resume_strategist,
        "preparer": interview_preparer,
        "fact_checker": fact_checker,
        "cover_writer": cover_writer,
    }
