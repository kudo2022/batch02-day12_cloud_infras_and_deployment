# Sample Run Data

These files are sample evidence logs from real API runs on 2026-06-02. They are included so instructors can demo report analysis without spending API quota again.

Files:

- `runs/real-v0_B_base_openrouter_20260602T082445084724.json`: base run with failures, useful for failure analysis demo.
- `runs/real-v1_B_base_openrouter_20260602T082625951099.json`: improved base run, 19/20 pass.
- `runs/real-v3_B_base_openrouter_20260602T082916299226.json`: base run after clarifying an ambiguous eval case, 20/20 pass.
- `runs/real-v6_B_base_openrouter_20260602T084059860979.json`: final base run, 20/20 pass.
- `runs/real-v6_B_extension_openrouter_20260602T083748159420.json`: final extension run, 10/10 pass.
- `run-analysis.csv`: flat parsed table from the sample run JSON files.
- `transcripts/real-v6_openrouter_20260602T084255167776.transcript.json`: sample chat transcript with `ask_user`, follow-up tool call, and parallel tools.
- `version_log.example.csv`: example of how a team can write version evidence.

Regenerate the CSV:

```bash
python scripts/parse_runs.py samples/runs --output samples/run-analysis.csv
```

These are examples only. Student teams still need to submit their own `runs/*.json`, `transcripts/*.transcript.json`, and `artifacts/version_log.csv`.
