# Tool Setup Guide

Use this guide before class. All keys go into `starter/.env`. Never commit `.env`.

Pricing and quotas can change. The classroom target below is current for this lab setup as of 2026-06-02; re-check the provider page before a new cohort.

## 1. Model Provider

Recommended provider:

```bash
OPENROUTER_API_KEY=...
```

Alternatives:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
```

Preflight:

```bash
cd starter
python scripts/preflight_provider.py --provider openrouter
```

## 2. Tavily — `web_search`

Use for web/news search.

- Docs/credits: https://docs.tavily.com/documentation/api-credits
- API key page: https://app.tavily.com
- Classroom target: free plan with 1,000 API credits/month.

Setup:

1. Sign in at https://app.tavily.com.
2. Create or copy API key.
3. Add to `starter/.env`:

```bash
TAVILY_API_KEY=tvly-...
```

Quick test:

```bash
python -c "from tools import web_search; print(web_search('AI news today', topic='news', timeframe='day', max_results=1)['items'][0]['title'])"
```

## 3. Firecrawl — `read_url`

Use for reading one specific URL.

- Pricing: https://www.firecrawl.dev/pricing
- Docs: https://docs.firecrawl.dev
- Classroom target: free plan with 1,000 credits/month.

Setup:

1. Sign up at https://www.firecrawl.dev.
2. Create API key.
3. Add to `starter/.env`:

```bash
FIRECRAWL_API_KEY=fc-...
```

Quick test:

```bash
python -c "from tools import read_url; print(read_url('https://openai.com/research/')['items'][0]['title'])"
```

## 4. RapidAPI Twitter API45 — `get_user_tweets`, `search_tweets`

Use for X/Twitter data.

- API page: https://rapidapi.com/alexanderxbx/api/twitter-api45
- Classroom target: free plan with 1,000 requests/month.

Setup:

1. Sign in to RapidAPI.
2. Open https://rapidapi.com/alexanderxbx/api/twitter-api45.
3. Subscribe to the API plan.
4. Copy RapidAPI key.
5. Add to `starter/.env`:

```bash
RAPIDAPI_KEY=...
RAPIDAPI_TWITTER_HOST=twitter-api45.p.rapidapi.com
```

Quick tests:

```bash
python -c "from tools import get_user_tweets; print(get_user_tweets('sama', limit=1)['items'][0]['title'])"
python -c "from tools import search_tweets; print(search_tweets('OpenAI', limit=1)['items'][0]['title'])"
```

## 5. arXiv Bonus — `arxiv_search`, `get_arxiv_paper_text`

No API key is required. arXiv is rate-limited, so the tools wait between requests and retry lightly on HTTP 429.

Setup:

```bash
ARXIV_USER_AGENT=AI20k-Day04-Research-Agent/1.0 (your-team-name)
```

Quick tests:

```bash
python -c "from tools import arxiv_search; print(arxiv_search('AI agent evaluation', max_results=1)['items'][0]['title'])"
python -c "from tools import get_arxiv_paper_text; print(get_arxiv_paper_text('1706.03762', max_pages=1)['chars_returned'])"
```

Generated paper files go under `starter/arxiv_papers/` and are ignored by git.

## 6. Telegram Bonus — `send_telegram`

Use only for bonus action. The agent must ask for confirmation before sending.

Official links:

- BotFather: https://t.me/BotFather
- Bot docs: https://core.telegram.org/bots

### Create Bot

1. Open Telegram.
2. Search for the official `@BotFather`.
3. Send:

```text
/newbot
```

4. Enter display name, for example:

```text
AI20k Research Bot
```

5. Enter username ending in `bot`, for example:

```text
ai20k_research_demo_bot
```

6. Copy the token BotFather returns.
7. Add to `starter/.env`:

```bash
TELEGRAM_BOT_TOKEN=1234567890:AA....
```

Never paste this token into reports, screenshots, chat logs, or GitHub.

### Create Channel

1. Create a private Telegram channel.
2. Add your bot as admin.
3. Grant permission to post messages.

### Get Chat ID

For a public channel:

```bash
TELEGRAM_CHAT_ID=@your_channel_username
```

For a private channel:

1. Add bot as admin.
2. Post a fresh message in the channel.
3. Run:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

4. Find:

```json
"chat": {"id": -1001234567890}
```

5. Add to `.env`:

```bash
TELEGRAM_CHAT_ID=-1001234567890
```

Direct tool test:

```bash
python -c "from tools import send_telegram; print(send_telegram('AI20k test message', confirmed=True))"
```

Agent behavior test:

```text
Đăng bản tin này lên Telegram giúp mình
```

Expected: `ask_user(response_type="yes_no")`, not `send_telegram`.

## Final Checklist

Before class, at least one person per group should have:

- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `RAPIDAPI_KEY`
- optional `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- optional `ARXIV_USER_AGENT`
- `python scripts/preflight_provider.py --provider openrouter` passes

