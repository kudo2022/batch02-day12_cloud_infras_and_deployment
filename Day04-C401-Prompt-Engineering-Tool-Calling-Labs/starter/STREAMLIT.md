# Streamlit UI

This lab now includes a Streamlit app at `starter/streamlit_app.py`.

## What it does

- Research chat workspace with transcript-backed conversation history
- Paper summary flow from DOI, arXiv ID, title, or URL
- Paper credibility heuristics using Semantic Scholar metadata, citation signals, and venue clues
- Live chat with the same provider, prompt, tools, and transcript format as `chat.py`

## Run locally

From `starter/`:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

If you use the bundled virtual environment on Windows:

```powershell
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe -m streamlit run streamlit_app.py
```

The app reads keys from:

- `.env`
- normal environment variables
- `st.secrets` on Streamlit Community Cloud

## Streamlit Community Cloud deploy

1. Push this project to GitHub.
2. In Streamlit Community Cloud, create a new app.
3. Set the app entry point to:

```text
Day04-C401-Prompt-Engineering-Tool-Calling-Labs/starter/streamlit_app.py
```

4. Add secrets in the app settings. You can copy the key names from:

```text
starter/.streamlit/secrets.toml.example
```

Minimum useful secrets:

- `OPENROUTER_API_KEY` or another provider key
- `SEMANTIC_SCHOLAR_API_KEY` optional but recommended for paper metadata stability
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `RAPIDAPI_KEY`

Optional:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Notes

- New live chat sessions are logged to `starter/transcripts/`.
- Paper credibility is heuristic. It should help triage papers, not replace critical reading.
