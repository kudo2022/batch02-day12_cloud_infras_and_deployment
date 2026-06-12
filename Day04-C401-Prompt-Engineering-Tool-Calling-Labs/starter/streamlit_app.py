from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

from chat import now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
RUNS_DIR = ROOT / "runs"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)

PROVIDER_OPTIONS = ["openrouter", "openai", "anthropic", "gemini"]
PROVIDER_ENV_KEYS = {
    "openrouter": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
}
TOOL_ENV_KEYS = [
    "SEMANTIC_SCHOLAR_API_KEY",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "RAPIDAPI_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]
DEFAULT_CHAT_TITLE = "Phien tra cuu cong nghe quan su moi"
TOOL_LABELS = {
    "web_search": "Web / Tin tuc",
    "read_url": "Doc URL",
    "search_tweets": "Thao luan X",
    "get_user_tweets": "Tai khoan X",
    "arxiv_search": "Bai bao arXiv",
    "paper_insights": "Phan tich bai bao",
}


def hydrate_env_from_streamlit_secrets() -> None:
    try:
        secrets_items = st.secrets.items()
    except Exception:
        return

    for key, value in secrets_items:
        if isinstance(value, (str, int, float, bool)):
            os.environ.setdefault(key, str(value))


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(54, 108, 242, 0.08), transparent 24%),
                radial-gradient(circle at bottom right, rgba(15, 118, 110, 0.08), transparent 20%),
                linear-gradient(180deg, #f4f7fb 0%, #eef3fb 100%);
        }

        [data-testid="stSidebar"] {
            background: #0f172a;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] details summary,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
            color: #e2e8f0 !important;
        }

        [data-testid="stSidebar"] details {
            border-color: rgba(226, 232, 240, 0.14);
            background: rgba(255, 255, 255, 0.03);
            border-radius: 14px;
        }

        .block-container {
            max-width: 100%;
            padding-top: 1rem;
            padding-bottom: 1.2rem;
        }

        .workspace-shell {
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.86);
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
            overflow: hidden;
        }

        .nav-panel {
            min-height: 82vh;
            background:
                linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
            border-right: 1px solid rgba(15, 23, 42, 0.08);
            padding: 1rem 0.95rem 1rem 0.95rem;
        }

        .chat-panel {
            min-height: 82vh;
            padding: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(248,250,252,0.96) 100%);
        }

        .nav-brand {
            border-radius: 18px;
            padding: 0.95rem 1rem;
            background: #0f172a;
            color: white;
            margin-bottom: 0.85rem;
        }

        .nav-brand h1 {
            font-size: 1.04rem;
            margin: 0;
        }

        .nav-brand p {
            margin: 0.3rem 0 0 0;
            color: rgba(255,255,255,0.72);
            font-size: 0.86rem;
        }

        .new-chat-button {
            border-radius: 16px;
            padding: 0.8rem 0.95rem;
            background: linear-gradient(135deg, #2563eb 0%, #4f7cff 100%);
            color: white;
            font-weight: 600;
        }

        .section-label {
            margin: 1rem 0 0.55rem 0;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #64748b;
        }

        .chat-header {
            padding: 1rem 1.4rem 0.95rem 1.4rem;
            border-bottom: 1px solid rgba(15, 23, 42, 0.08);
            background: rgba(255, 255, 255, 0.78);
            backdrop-filter: blur(8px);
        }

        .chat-header h2 {
            margin: 0;
            font-size: 1.55rem;
            color: #0f172a;
        }

        .status-row {
            margin-top: 0.35rem;
            display: flex;
            gap: 0.55rem;
            align-items: center;
            color: #475569;
            font-size: 0.92rem;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #10b981;
            display: inline-block;
            box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.13);
        }

        .insight-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            padding: 1rem 1.4rem 0.25rem 1.4rem;
        }

        .insight-card {
            border: 1px solid rgba(15, 23, 42, 0.07);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            background: rgba(255,255,255,0.82);
            box-shadow: 0 14px 34px rgba(15,23,42,0.05);
        }

        .insight-card .eyebrow {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748b;
            margin-bottom: 0.35rem;
        }

        .insight-card .value {
            font-size: 1.1rem;
            font-weight: 700;
            color: #0f172a;
        }

        .insight-note {
            margin: 0.4rem 1.4rem 0 1.4rem;
            padding: 0.8rem 0.95rem;
            border-radius: 16px;
            background: rgba(15, 118, 110, 0.08);
            color: #134e4a;
            border: 1px solid rgba(15, 118, 110, 0.12);
            font-size: 0.92rem;
        }

        .messages-wrap {
            padding: 0.9rem 1.4rem 0.4rem 1.4rem;
        }

        .welcome-hero {
            min-height: 50vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 2rem 1rem;
        }

        .welcome-card {
            max-width: 740px;
        }

        .welcome-badge {
            width: 76px;
            height: 76px;
            margin: 0 auto 1rem auto;
            border-radius: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
            color: #2563eb;
            font-size: 2rem;
            font-weight: 700;
        }

        .welcome-card h3 {
            margin: 0 0 0.6rem 0;
            font-size: 2.2rem;
            line-height: 1.12;
            color: #0f172a;
        }

        .welcome-card p {
            margin: 0 auto 1.1rem auto;
            max-width: 650px;
            font-size: 1rem;
            color: #475569;
        }

        .suggestion-card {
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 18px;
            padding: 1rem;
            background: rgba(255,255,255,0.84);
            box-shadow: 0 14px 34px rgba(15,23,42,0.04);
            height: 100%;
        }

        .composer-shell {
            padding: 0.3rem 1.4rem 1.2rem 1.4rem;
        }

        .composer-note {
            text-align: center;
            color: #64748b;
            font-size: 0.88rem;
            margin-top: 0.35rem;
        }

        .mono-note {
            font-family: "IBM Plex Mono", monospace;
        }

        div[data-testid="stButton"] > button {
            border-radius: 14px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: rgba(255,255,255,0.9);
        }

        div[data-testid="stForm"] {
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 22px;
            background: rgba(255, 255, 255, 0.96);
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
            padding: 0.85rem 0.95rem 0.55rem 0.95rem;
        }

        div[data-testid="stTextInput"] input {
            border-radius: 14px !important;
        }

        @media (max-width: 1100px) {
            .insight-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def config_signature(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, default=str)


def default_provider_index() -> int:
    for idx, provider in enumerate(PROVIDER_OPTIONS):
        required_keys = PROVIDER_ENV_KEYS.get(provider, [])
        if required_keys and all(os.getenv(key) for key in required_keys):
            return idx
    return 0


def json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sorted_json_files(directory: Path, suffix: str = "*.json") -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(suffix), key=lambda item: item.stat().st_mtime, reverse=True)


def build_transcript_bundle(config: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    provider = make_provider(config["provider"])
    selected_model = config["model"] or getattr(provider, "default_model", None)
    artifact_version = build_artifact_version(
        config["version"],
        Path(config["system_prompt"]),
        Path(config["tools"]),
    )
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join(
        [
            safe_slug(config["version"]),
            safe_slug(config["provider"]),
            timestamp,
        ]
    )
    transcript_path = Path(config["transcripts_dir"]) / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        "title": DEFAULT_CHAT_TITLE,
        **artifact_version_dict(artifact_version),
        "provider": config["provider"],
        "model": selected_model,
        "system_prompt": config["system_prompt"],
        "tools": config["tools"],
        "history_window": config["history_window"],
        "max_tool_rounds": config["max_tool_rounds"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return transcript, transcript_path


def derive_title(user_text: str) -> str:
    cleaned = " ".join((user_text or "").split())
    if not cleaned:
        return DEFAULT_CHAT_TITLE
    trimmed = cleaned[:58].rstrip(" ,.;:-")
    return trimmed if len(cleaned) <= 58 else f"{trimmed}..."


def history_from_turns(turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for turn in turns:
        user_text = turn.get("user")
        assistant_text = turn.get("assistant_text")
        if user_text:
            history.append({"role": "user", "content": user_text})
        if assistant_text:
            history.append({"role": "assistant", "content": assistant_text})
    return history


def save_transcript() -> None:
    transcript = st.session_state.transcript
    transcript_path = Path(st.session_state.transcript_path)
    write_transcript(transcript_path, transcript)


def reset_chat_session(config: dict[str, Any], *, title: str | None = None) -> None:
    transcript, transcript_path = build_transcript_bundle(config)
    if title:
        transcript["title"] = title
    st.session_state.chat_turns = []
    st.session_state.chat_history = []
    st.session_state.transcript = transcript
    st.session_state.transcript_path = str(transcript_path)
    st.session_state.active_chat_config = dict(config)
    st.session_state.active_chat_signature = config_signature(config)
    save_transcript()


def ensure_chat_session(config: dict[str, Any]) -> None:
    if "active_chat_signature" not in st.session_state:
        reset_chat_session(config)


def load_chat_session_from_file(path: Path) -> None:
    transcript = load_json(path)
    turns = transcript.get("turns", [])
    restored_config = {
        "provider": transcript.get("provider", "openrouter"),
        "model": transcript.get("model") or "",
        "version": transcript.get("version", "v0"),
        "history_window": int(transcript.get("history_window", 5)),
        "max_tool_rounds": int(transcript.get("max_tool_rounds", 4)),
        "system_prompt": transcript.get("system_prompt", str(ARTIFACTS_DIR / "system_prompt.md")),
        "tools": transcript.get("tools", str(ARTIFACTS_DIR / "tools.yaml")),
        "runs_dir": str(RUNS_DIR),
        "transcripts_dir": str(TRANSCRIPTS_DIR),
    }
    st.session_state.chat_turns = turns
    st.session_state.chat_history = history_from_turns(turns)
    st.session_state.transcript = transcript
    st.session_state.transcript_path = str(path)
    st.session_state.active_chat_config = restored_config
    st.session_state.active_chat_signature = config_signature(restored_config)


def parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def transcript_summary(path: Path) -> dict[str, Any]:
    try:
        payload = load_json(path)
    except Exception:
        payload = {}
    turns = payload.get("turns", [])
    title = payload.get("title")
    if not title:
        if turns and turns[0].get("user"):
            title = derive_title(turns[0]["user"])
        else:
            title = path.stem
    created_at = parse_iso_dt(payload.get("created_at")) or datetime.fromtimestamp(path.stat().st_mtime)
    return {
        "path": path,
        "title": title,
        "created_at": created_at,
        "turn_count": len(turns),
        "provider": payload.get("provider", ""),
    }


def matches_time_filter(created_at: datetime, filter_name: str) -> bool:
    now = datetime.now()
    if filter_name == "Hom nay":
        return created_at.date() == now.date()
    if filter_name == "7 ngay qua":
        return created_at >= now - timedelta(days=7)
    if filter_name == "30 ngay qua":
        return created_at >= now - timedelta(days=30)
    return True


def history_bucket(created_at: datetime) -> str:
    now = datetime.now()
    if created_at.date() == now.date():
        return "Hom nay"
    if created_at >= now - timedelta(days=7):
        return "Tuan nay"
    return "Cu hon"


def list_transcripts(directory: Path, search_text: str, time_filter: str) -> list[dict[str, Any]]:
    summaries = [transcript_summary(path) for path in sorted_json_files(directory, "*.transcript.json")]
    filtered: list[dict[str, Any]] = []
    for item in summaries:
        title = item["title"].lower()
        if search_text and search_text.lower() not in title:
            continue
        if not matches_time_filter(item["created_at"], time_filter):
            continue
        filtered.append(item)
    return filtered


def update_transcript_title(user_text: str) -> None:
    transcript = st.session_state.transcript
    if not transcript.get("title") or transcript.get("title") == DEFAULT_CHAT_TITLE:
        transcript["title"] = derive_title(user_text)


def clean_text(value: str | None, limit: int = 220) -> str:
    cleaned = " ".join((value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def latest_search_snapshot() -> dict[str, Any] | None:
    for turn in reversed(st.session_state.get("chat_turns", [])):
        for event in reversed(turn.get("tool_events", [])):
            tool_name = event.get("tool")
            result = event.get("result") or {}
            if tool_name in TOOL_LABELS and not result.get("error"):
                return event
    return None


def run_streamlit_turn(user_text: str) -> None:
    config = st.session_state.active_chat_config
    turn_record: dict[str, Any] = {
        "turn_index": len(st.session_state.chat_turns) + 1,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    try:
        system_prompt_path = Path(config["system_prompt"])
        tools_path = Path(config["tools"])
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(tools_path)
        openai_tools = to_openai_tools(tool_declarations)
        provider = make_provider(config["provider"])
        messages = [
            {"role": "system", "content": system_prompt},
            *trim_history(st.session_state.chat_history, int(config["history_window"])),
            {"role": "user", "content": user_text},
        ]
        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=config["model"] or None,
            max_tool_rounds=int(config["max_tool_rounds"]),
        )
        turn_record.update(result)
        assistant_text = result["assistant_text"]
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
    except Exception as exc:
        turn_record.update(
            {
                "status": "provider_error",
                "assistant_text": f"{type(exc).__name__}: {str(exc)}",
                "error": f"{type(exc).__name__}: {str(exc)}",
            }
        )
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        st.session_state.chat_history.append({"role": "assistant", "content": turn_record["assistant_text"]})

    turn_record["ended_at"] = now_iso()
    update_transcript_title(user_text)
    st.session_state.chat_turns.append(turn_record)
    st.session_state.transcript["turns"].append(turn_record)
    save_transcript()


def render_tool_trace(turn: dict[str, Any]) -> None:
    if not turn.get("rounds") and not turn.get("tool_events"):
        return
    with st.expander("Dấu vết tool", expanded=False):
        for round_record in turn.get("rounds", []):
            st.markdown(f"**Lượt {round_record['round']}**")
            if round_record.get("assistant_text"):
                st.write(round_record["assistant_text"])
            if round_record.get("tool_calls"):
                st.code(json_block(round_record["tool_calls"]), language="json")
            if round_record.get("tool_results"):
                st.code(json_block(round_record["tool_results"]), language="json")
        if turn.get("status") == "provider_error" and turn.get("error"):
            st.error(turn["error"])


def render_sidebar_controls() -> dict[str, Any]:
    st.sidebar.markdown("## Cau Hinh Agent")
    provider = st.sidebar.selectbox("Provider", PROVIDER_OPTIONS, index=default_provider_index())
    model = st.sidebar.text_input("Model tuy chinh", value="")
    version = st.sidebar.text_input("Nhan phien ban", value="v0")
    history_window = st.sidebar.slider("So cap lich su", 1, 10, 5)
    max_tool_rounds = st.sidebar.slider("So vong tool toi da", 1, 8, 4)

    st.sidebar.caption("Neu man hinh nho, hay dong sidebar de quay lai khung chat.")

    missing_provider_keys = [key for key in PROVIDER_ENV_KEYS.get(provider, []) if not os.getenv(key)]
    if missing_provider_keys:
        missing_text = ", ".join(f"`{key}`" for key in missing_provider_keys)
        st.sidebar.warning(f"Da chon {provider} nhung thieu khoa moi truong bat buoc: {missing_text}")

    with st.sidebar.expander("Duong dan", expanded=False):
        system_prompt = st.text_input("System prompt", value=str(ARTIFACTS_DIR / "system_prompt.md"))
        tools = st.text_input("Tools YAML", value=str(ARTIFACTS_DIR / "tools.yaml"))
        runs_dir = st.text_input("Thu muc runs", value=str(RUNS_DIR))
        transcripts_dir = st.text_input("Thu muc transcripts", value=str(TRANSCRIPTS_DIR))

    with st.sidebar.expander("Trang thai moi truong", expanded=False):
        for key in PROVIDER_ENV_KEYS.get(provider, []):
            st.write(f"`{key}`: {'ready' if os.getenv(key) else 'missing'}")
        for key in TOOL_ENV_KEYS:
            st.write(f"`{key}`: {'ready' if os.getenv(key) else 'missing'}")

    with st.sidebar.expander("Ghi chu tac vu", expanded=False):
        st.caption("Uu tien web hoac news cho thong tin moi, va dung URL cu the neu can doc sau.")
        st.caption("Co the tim bai bao ky thuat cong khai bang DOI, arXiv, tieu de hoac URL.")
        st.caption("Chi ho tro phan tich an toan o muc cao, khong huong dan che tao hay van hanh vu khi.")

    return {
        "provider": provider,
        "model": model.strip(),
        "version": version.strip() or "v0",
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "system_prompt": system_prompt,
        "tools": tools,
        "runs_dir": runs_dir,
        "transcripts_dir": transcripts_dir,
    }


def render_history_nav(config: dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="nav-panel">
          <div class="nav-brand">
            <h1>Military Tech Search</h1>
            <p>Tra cuu cong nghe quan su tu nguon cong khai va tra loi bang tieng Viet.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("+ Cuoc tro chuyen moi", key="new_chat_button", use_container_width=True, type="primary"):
        reset_chat_session(config)
        st.rerun()

    search_text = st.text_input("Tim lich su", value="", placeholder="Tim trong cac cuoc tro chuyen...")
    time_filter = st.selectbox("Thoi gian", ["Tat ca", "Hom nay", "7 ngay qua", "30 ngay qua"], index=0)

    st.markdown('<div class="section-label">Hoi thoai</div>', unsafe_allow_html=True)
    transcripts = list_transcripts(Path(config["transcripts_dir"]), search_text, time_filter)
    active_path = st.session_state.get("transcript_path", "")

    buckets: dict[str, list[dict[str, Any]]] = {"Hom nay": [], "Tuan nay": [], "Cu hon": []}
    for item in transcripts:
        buckets[history_bucket(item["created_at"])].append(item)

    for label, items in buckets.items():
        if not items:
            continue
        st.caption(label)
        for item in items:
            button_type = "primary" if str(item["path"]) == active_path else "secondary"
            subtitle = f"{item['created_at'].strftime('%d/%m %H:%M')} | {item['turn_count']} luot"
            if st.button(f"{item['title']}\n{subtitle}", key=f"history-{item['path'].name}", use_container_width=True, type=button_type):
                load_chat_session_from_file(item["path"])
                st.rerun()

    st.markdown('<div class="section-label">Khong gian lam viec</div>', unsafe_allow_html=True)
    st.caption("Danh cho tra cuu cong nghe quoc phong")
    st.caption("Ho tro web/news, URL cu the, bai bao ky thuat, va tong hop nguon.")
    if st.session_state.get("active_chat_signature") != config_signature(config):
        st.info("Thay doi trong sidebar se duoc ap dung khi bat dau cuoc tro chuyen moi.")

    st.markdown(
        f"""
        <div style="margin-top: 1rem; padding-top: 0.85rem; border-top: 1px solid rgba(15,23,42,0.08);">
          <div style="font-weight: 700; color: #0f172a;">Defense Analyst</div>
          <div style="color: #64748b; font-size: 0.92rem;">Workspace co luu transcript</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_header(config: dict[str, Any]) -> None:
    transcript = st.session_state.transcript
    title = transcript.get("title") or DEFAULT_CHAT_TITLE
    provider = st.session_state.active_chat_config.get("provider", config["provider"])
    model = st.session_state.active_chat_config.get("model") or "provider default"
    st.markdown(
        f"""
        <div class="chat-header">
          <h2>{title}</h2>
          <div class="status-row">
            <span class="status-dot"></span>
            <span>Phien tra cuu dang hoat dong</span>
            <span>|</span>
            <span>{provider}</span>
            <span>|</span>
            <span>{model}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_latest_insight() -> None:
    snapshot = latest_search_snapshot()
    if not snapshot:
        return

    tool_name = snapshot.get("tool", "")
    result = snapshot.get("result", {}) or {}
    items = result.get("items") or []
    query = result.get("query") or result.get("url") or result.get("screenname") or result.get("paper_ref") or "-"

    if tool_name == "paper_insights":
        paper = result.get("paper", {})
        credibility = result.get("credibility", {})
        st.markdown(
            f"""
            <div class="insight-grid">
              <div class="insight-card">
                <div class="eyebrow">Loai tra cuu</div>
                <div class="value">{TOOL_LABELS.get(tool_name, tool_name)}</div>
              </div>
              <div class="insight-card">
                <div class="eyebrow">Do tin cay</div>
                <div class="value">{credibility.get('level', 'n/a')}</div>
              </div>
              <div class="insight-card">
                <div class="eyebrow">Trich dan</div>
                <div class="value">{paper.get('citation_count', 0)}</div>
              </div>
              <div class="insight-card">
                <div class="eyebrow">Venue / Nam</div>
                <div class="value">{paper.get('venue') or 'Unknown'} | {paper.get('year') or 'n/a'}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        reasons = credibility.get("reasons") or []
        if reasons:
            st.markdown(
                f'<div class="insight-note"><strong>Ghi chu moi nhat:</strong> {clean_text(reasons[0], 220)}</div>',
                unsafe_allow_html=True,
            )
        return

    top_item = items[0] if items else {}
    top_source = top_item.get("source") or "-"
    top_title = top_item.get("title") or "Khong co tieu de"
    st.markdown(
        f"""
        <div class="insight-grid">
          <div class="insight-card">
            <div class="eyebrow">Loai tra cuu</div>
            <div class="value">{TOOL_LABELS.get(tool_name, tool_name)}</div>
          </div>
          <div class="insight-card">
            <div class="eyebrow">So ket qua</div>
            <div class="value">{len(items)}</div>
          </div>
          <div class="insight-card">
            <div class="eyebrow">Chu de</div>
            <div class="value">{clean_text(str(query), 42)}</div>
          </div>
          <div class="insight-card">
            <div class="eyebrow">Nguon dau</div>
            <div class="value">{clean_text(str(top_source), 24)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="insight-note"><strong>Ket qua noi bat:</strong> {clean_text(top_title, 180)}</div>',
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="welcome-hero">
          <div class="welcome-card">
            <div class="welcome-badge">&#9889;</div>
            <h3>Hom nay ban muon tra cuu cong nghe quan su nao?</h3>
            <p>Ban co the yeu cau tong hop tin moi, so sanh cong nghe o muc cong khai, doc mot URL cu the, hoac tim bai bao ky thuat lien quan.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    suggestion_cols = st.columns(3, gap="large")
    suggestions = [
        (
            "Tong hop tin moi",
            "Hay tong hop cac tin tuc 7 ngay gan day ve UAV quan su va neu 5 xu huong chinh.",
            "Phu hop cho cap nhat nhanh theo chu de.",
        ),
        (
            "So sanh cong nghe",
            "So sanh o muc cong khai giua radar AESA tren F-35, J-20 va KF-21: vai tro, diem manh va gioi han.",
            "Chi tong hop thong tin cong khai, khong suy doan qua muc.",
        ),
        (
            "Tim nghien cuu ky thuat",
            "Tim cac bai arXiv gan day ve tu hanh, cam bien, hoac ISR lien quan den UAV quan su tu nguon cong khai.",
            "Dung khi can dao sau goc nhin hoc thuat.",
        ),
    ]

    for column, (title, prompt_text, helper) in zip(suggestion_cols, suggestions):
        with column:
            st.markdown(f'<div class="suggestion-card"><strong>{title}</strong><p style="color:#64748b; margin:0.45rem 0 0.8rem 0;">{helper}</p></div>', unsafe_allow_html=True)
            if st.button(title, key=f"suggest-{title}", use_container_width=True):
                run_streamlit_turn(prompt_text)
                st.rerun()


def render_turn(turn: dict[str, Any]) -> None:
    with st.chat_message("user"):
        st.write(turn.get("user", ""))
    with st.chat_message("assistant"):
        st.write(turn.get("assistant_text") or "")

        for event in turn.get("tool_events", []):
            result = event.get("result", {})
            tool_name = event.get("tool")
            if tool_name == "paper_insights":
                paper = result.get("paper", {})
                summary = result.get("summary", {})
                credibility = result.get("credibility", {})
                st.markdown(
                    f"""
                    <div class="suggestion-card" style="margin-top: 0.45rem;">
                      <strong>{paper.get('title', 'Paper insight')}</strong>
                      <p style="margin:0.45rem 0 0.6rem 0; color:#475569;">{clean_text(summary.get('executive_summary', ''), 220)}</p>
                      <p style="margin:0; color:#0f172a;"><strong>Do tin cay:</strong> {credibility.get('level', 'n/a')} (score {credibility.get('score', 'n/a')})</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                continue

            if tool_name not in TOOL_LABELS:
                continue

            items = result.get("items") or []
            if not items:
                continue

            top_item = items[0]
            st.markdown(
                f"""
                <div class="suggestion-card" style="margin-top: 0.45rem;">
                  <strong>{clean_text(top_item.get('title', 'Ket qua tra cuu'), 140)}</strong>
                  <p style="margin:0.45rem 0 0.6rem 0; color:#475569;">{clean_text(top_item.get('summary', ''), 240)}</p>
                  <p style="margin:0; color:#0f172a;"><strong>Nguon:</strong> {top_item.get('source', 'n/a')} | <strong>Loai:</strong> {TOOL_LABELS.get(tool_name, tool_name)} | <strong>So muc:</strong> {len(items)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        render_tool_trace(turn)


def render_messages_area() -> None:
    st.markdown('<div class="messages-wrap">', unsafe_allow_html=True)
    if not st.session_state.chat_turns:
        render_empty_state()
    else:
        for turn in st.session_state.chat_turns:
            render_turn(turn)
    st.markdown("</div>", unsafe_allow_html=True)


def render_composer() -> None:
    st.markdown('<div class="composer-shell">', unsafe_allow_html=True)
    with st.form("military_search_composer", clear_on_submit=True):
        prompt = st.text_input(
            "Tin nhan",
            value="",
            label_visibility="collapsed",
            placeholder="Hoi ve UAV, radar, ISR, EW, dan URL can doc, hoac yeu cau tong hop tin moi...",
        )
        note_col, send_col = st.columns([0.8, 0.2])
        with note_col:
            st.caption("Ho tro web/news, URL cu the, DOI, arXiv, tieu de bai bao, va ghi chu markdown.")
        with send_col:
            submitted = st.form_submit_button("Gui", use_container_width=True, type="primary")
    if submitted and prompt.strip():
        with st.spinner("Dang chay agent tra cuu..."):
            run_streamlit_turn(prompt.strip())
        st.rerun()
    st.markdown('<div class="composer-note">Agent chi dung nguon cong khai va van co the sai. Hay kiem tra lai cac khang dinh quan trong.</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_workspace(config: dict[str, Any]) -> None:
    left_col, right_col = st.columns([0.26, 0.74], gap="small")

    with left_col:
        render_history_nav(config)

    with right_col:
        st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
        render_chat_header(config)
        render_latest_insight()
        render_messages_area()
        render_composer()
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="Military Tech Search Workspace",
        page_icon="M",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    hydrate_env_from_streamlit_secrets()
    inject_css()

    config = render_sidebar_controls()
    ensure_chat_session(config)

    st.markdown('<div class="workspace-shell">', unsafe_allow_html=True)
    render_workspace(config)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
