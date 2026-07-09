# Newsletter Agent

A mini autonomous AI agent that researches recent AI agent news, summarizes the best stories, writes a weekly newsletter, critiques its own draft, improves it, and simulates sending by saving HTML and Markdown files.

## What It Does

- Accepts a plain English goal such as:
  `Create a weekly newsletter on latest AI agent news and send it to our subscribers.`
- Uses a LangGraph workflow for planning, research, writing, review, revision, and output.
- Uses public Google News RSS search and article scraping for research.
- Uses an LLM through LangChain when configured, with a deterministic fallback summarizer when no key is present.
- Supports two modes:
  - `autonomous`: one call completes the full newsletter and saves the simulated email.
  - `human`: first call pauses with a draft and critique; submit feedback to finalize.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `GOOGLE_API_KEY` for Gemini (free at [aistudio.google.com](https://aistudio.google.com)), `OPENAI_API_KEY` for OpenAI, or `OLLAMA_MODEL` for local Ollama. If no key is set, the app still runs with local extractive summaries.

## Run

```powershell
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

Run the test suite with:

```powershell
pip install -r requirements-dev.txt
pytest -q
```

## One-Function Agent Call

```python
from app.newsletter_agent.agent import run_newsletter_agent

result = run_newsletter_agent(
    "Create a weekly newsletter on latest AI agent news and send it to our subscribers.",
    mode="autonomous",
)

print(result["subject"])
print(result["output_paths"])
```

You can also run it from the command line:

```powershell
python run_agent.py --mode autonomous
```

## Tool Use Shown

The response includes a `tool_log` with the major tool calls:

- `planner`
- `web_search`
- `article_fetcher`
- `summarizer`
- `html_generator`
- `self_critique`
- `content_editor`
- `simulated_sender`

Generated newsletters are saved under `outputs/`.

## Deploy

The repository includes a Render Blueprint in `render.yaml`.

1. Push the project to a public GitHub repository.
2. In Render, choose **New > Blueprint** and connect the repository.
3. Set `OPENAI_API_KEY` when prompted, or leave it empty to use local extractive summaries.
4. Deploy and verify the Streamlit app loads at the provided URL.

Render's free filesystem is ephemeral, so simulated newsletter files may disappear after a restart. The generated content remains visible in the browser response.
