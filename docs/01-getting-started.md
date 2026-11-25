# 1. Getting Started

## What you need
- Python 3.10 – 3.13
- A free Groq API key: https://console.groq.com/keys
- (Optional) A GitHub personal access token, to avoid GitHub API rate limits

## Step-by-step setup

1. **Unzip the project and open a terminal inside it**
   ```bash
   cd job-application-crew
   ```
2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Create your `.env` file**
   ```bash
   cp .env.example .env            # Windows: copy .env.example .env
   ```
   Open `.env` and set:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxx
   GROQ_MODEL=groq/llama-3.3-70b-versatile
   GITHUB_TOKEN=            # optional
   ```
5. **Start the app**
   ```bash
   python run.py
   ```
6. **Open** http://127.0.0.1:8000 in your browser.

## Checking it works
Visit http://127.0.0.1:8000/api/health. You should see `{"status":"ok"}`.
