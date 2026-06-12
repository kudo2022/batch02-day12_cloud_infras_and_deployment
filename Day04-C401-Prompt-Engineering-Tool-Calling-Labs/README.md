# Day 04 Lab v2 — Research Agent Tool Eval

## Brief

Trong lab này, nhóm build một research agent nhỏ nhưng chạy thật. Agent nhận request của user, chọn đúng tool, truyền đúng arguments, chạy tool thật, lưu full JSON log, rồi dùng log đó để tối ưu prompt/tool declaration qua nhiều version.

Điều cần học không phải là "chatbot trả lời hay". Điều cần học là vòng lặp evidence-driven:

1. Chạy baseline bằng API thật.
2. Đọc run JSON để biết sai tool, sai args, thiếu hỏi lại, hoặc gọi tool thừa.
3. Sửa `artifacts/system_prompt.md` hoặc `artifacts/tools.yaml`.
4. Chạy lại và ghi versioning.
5. Tự viết thêm eval case để đo những lỗi nhóm quan tâm.
6. Viết report dựa trên log thật, không dựa vào cảm giác.

## Scope

Core bắt buộc:

- Setup chạy được bằng provider thật.
- Agent có ít nhất 5 tool trong `artifacts/tools.yaml`.
- Chạy base eval.
- Tối ưu ít nhất 3 vòng sau baseline: `v1`, `v2`, `v3`.
- Ghi `artifacts/version_log.csv`.
- Tự viết thêm ít nhất 5 eval case vào `data/eval_group.json`.
- Nộp run JSON, transcript JSON, report.

Bonus:

- Action tool: `send_telegram`, có confirmation trước khi gửi.
- Extra tools: `search_company_policy`, `arxiv_search`, `get_arxiv_paper_text`.
- UI: Streamlit hoặc Vercel.

## Folder Map

```text
starter/
  agent.py                    # one-shot model -> tool calls -> tool execution
  chat.py                     # interactive chat, multi-round tools, transcript JSON
  run_eval.py                 # eval routing + args, writes runs/*.json
  versioning.py               # prompt/tool hash
  artifacts/
    system_prompt.md          # student edits
    tools.yaml                # student edits
    version_log.csv           # student fills
    REPORT.md                 # final report template
  data/
    eval_base.json            # fixed base eval, do not edit
    eval_group.json           # team adds at least 5 cases
    eval_research_extension.json
  tools/
    README.md                 # tool folder contract
    <tool_name>/
      TOOL.md                 # frontmatter + notes
      tool.py                 # self-contained implementation
  company_policy/             # local markdown KB for bonus policy tool
  providers/                  # OpenRouter/OpenAI/Anthropic/Gemini adapters
  scripts/preflight_provider.py
  samples/                    # instructor sample run logs + parsed CSV
```

## Tool Tracks

Core tools:

- `ask_user`: ask for missing info or confirmation.
- `get_user_tweets`: get recent tweets from a known account.
- `search_tweets`: search tweets by topic.
- `web_search`: search web/news with Tavily.
- `read_url`: read one URL with Firecrawl.
- `render_digest`: format gathered items into markdown.

Bonus tools:

- `send_telegram`: action tool, only after explicit confirmation.
- `search_company_policy`: local company policy markdown search.
- `arxiv_search`: search arXiv papers.
- `get_arxiv_paper_text`: download arXiv PDF and extract text locally.

Each tool lives in its own folder under `starter/tools/<tool_name>/`.

## Setup

Run from `starter/`:

```bash
cd starter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`. Minimum recommended:

```bash
OPENROUTER_API_KEY=...
TAVILY_API_KEY=...
FIRECRAWL_API_KEY=...
RAPIDAPI_KEY=...
RAPIDAPI_TWITTER_HOST=twitter-api45.p.rapidapi.com
```

Tool setup details are in [TOOL-SETUP.md](TOOL-SETUP.md).

Preflight:

```bash
python scripts/preflight_provider.py --provider openrouter
```

If preflight fails, fix provider key, dependency, or network before running eval.

## Step 1 — Run Baseline

Run the fixed base eval as `v0`:

```bash
python run_eval.py \
  --provider openrouter \
  --version v0 \
  --suite base \
  --eval-cases data/eval_base.json
```

Output is saved to `runs/*.json`. Read:

- `summary.case_accuracy`
- `summary.tool_routing_accuracy`
- `summary.argument_accuracy`
- `summary.multiturn_accuracy`
- `results[*].result.failures`
- `results[*].result.observed_mismatch`

The run JSON also stores:

- `artifact_version`
- `prompt_hash`
- `tools_hash`
- actual tool calls
- actual tool results

That is the evidence for your report.

Optional: parse run JSON into a flat CSV table for analysis:

```bash
python scripts/parse_runs.py runs/ --output analysis/base_runs.csv
```

## Step 2 — Fix One Thing

Edit only:

- `artifacts/system_prompt.md`
- `artifacts/tools.yaml`

Do not edit `data/eval_base.json`.

Typical fixes:

- Wrong `get_user_tweets` vs `search_tweets`: clarify "FROM account" vs "ABOUT topic".
- Wrong timeframe: map "hôm nay" to `day`, "tuần này" to `week`.
- Missing info: force `ask_user` instead of guessing.
- Wrong boundary: never call `send_telegram` unless user confirmed.

Change one hypothesis at a time so the version log is meaningful.

## Step 3 — Run 3 Optimization Versions

Run at least three improved versions:

```bash
python run_eval.py --provider openrouter --version v1 --suite base --eval-cases data/eval_base.json
python run_eval.py --provider openrouter --version v2 --suite base --eval-cases data/eval_base.json
python run_eval.py --provider openrouter --version v3 --suite base --eval-cases data/eval_base.json
```

After each run, fill `artifacts/version_log.csv`:

```text
version,author,changed_artifact,artifact_version,prompt_hash,tools_hash,reason,hypothesis,metric_before,metric_after,run_file
```

Use hashes and run file paths from the eval output.

## Step 4 — Add Team Eval

Add at least 5 cases to `data/eval_group.json`.

Each case needs:

- `id`
- `phase`: always `"B"`
- `query` or `turns`
- `failure_type`: one of `wrong_tool`, `wrong_arg_value`, `wrong_boundary`, `unnecessary_tool`, `out_of_scope`, `missing_info`
- `expect`: `tool_calls` or `no_tool`
- `metadata.what_it_tests`

Run:

```bash
python run_eval.py \
  --provider openrouter \
  --version v3 \
  --suite group \
  --eval-cases data/eval_group.json
```

Optional extension eval:

```bash
python run_eval.py \
  --provider openrouter \
  --version v3 \
  --suite extension \
  --eval-cases data/eval_research_extension.json
```

## Step 5 — Chat Live

`chat.py` is for live multi-round interaction. It logs every turn to `transcripts/*.transcript.json`.

```bash
python chat.py --provider openrouter --version v3
```

Try at least 3 live turns:

- A normal research request.
- A missing-info request that triggers `ask_user`, then a follow-up answer.
- A digest request after tool results exist.

If doing bonus, test Telegram confirmation:

```text
Đăng bản tin này lên Telegram giúp mình
```

Expected: agent calls `ask_user(response_type="yes_no")`, not `send_telegram`.

## Submit

Submit `starter/` with:

- `artifacts/system_prompt.md`
- `artifacts/tools.yaml`
- `artifacts/version_log.csv` with at least `v0`, `v1`, `v2`, `v3`
- `artifacts/REPORT.md`
- `data/eval_group.json` with at least 5 team cases
- `runs/*.json`
- `analysis/*.csv` if you parsed run logs
- `transcripts/*.transcript.json`
- code changes if your team added or changed tools/UI

Do not submit `.env` or API keys.

## Timeline 4h

- 0:00-0:25 setup, keys, preflight.
- 0:25-0:55 run baseline, inspect JSON.
- 0:55-1:45 improve prompt/tools for v1-v2.
- 1:45-2:15 write team eval cases.
- 2:15-2:45 run v3 + group eval.
- 2:45-3:20 chat live + transcript.
- 3:20-3:50 report.
- 3:50-4:00 package and final sanity check.
