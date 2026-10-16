"""UT Study Prep — a lightweight Streamlit companion for final-exam revision."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import html
import json
import os
from typing import Any

import streamlit as st

from ut_study_prep.ai import DEFAULT_MODEL, build_ai_study_pack
from ut_study_prep.analysis import build_local_study_pack
from ut_study_prep.models import StudyPack
from ut_study_prep.tts import speech_controls


st.set_page_config(
    page_title="UT Study Prep",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_CSS = """
<style>
  :root {
    --ink: #172336;
    --muted: #67716f;
    --forest: #123d3a;
    --forest-soft: #e7efec;
    --cream: #fbf8f1;
    --coral: #d45c3b;
    --line: #dfe4e2;
  }

  .stApp { background: var(--cream); color: var(--ink); }
  [data-testid="stHeader"] { background: rgba(251, 248, 241, .82); }
  [data-testid="stSidebar"] { background: #f0f4f1; border-right: 1px solid var(--line); }
  [data-testid="stSidebar"] hr { border-color: #d8dfdc; }
  .block-container { max-width: 1180px; padding-top: 2.3rem; padding-bottom: 4rem; }

  h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
  h1 { font-size: clamp(2.3rem, 5vw, 4.25rem) !important; line-height: .98 !important; }
  h2 { margin-top: 1.8rem !important; }
  p, label { color: var(--ink); }

  .hero-kicker { color: var(--coral); font-size: .76rem; font-weight: 800; letter-spacing: .16em; }
  .hero-copy { max-width: 760px; color: var(--muted); font-size: 1.08rem; line-height: 1.65; margin: .8rem 0 1.6rem; }
  .hero-rule { height: 4px; width: 72px; border-radius: 99px; background: var(--coral); margin: 1.25rem 0; }

  .session-banner {
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    background: var(--forest); color: white; border-radius: 20px; padding: 1.15rem 1.3rem;
    margin: .2rem 0 1.35rem;
  }
  .session-banner strong { color: white; font-size: 1.18rem; }
  .session-banner span { color: #c9dad6; font-size: .9rem; }
  .session-number {
    display: grid; place-items: center; min-width: 48px; height: 48px; border-radius: 14px;
    color: var(--forest); background: #f5c86d; font-weight: 900; font-size: 1.18rem;
  }
  .session-banner-copy { flex: 1; display: grid; gap: .15rem; }

  .note-card {
    background: white; border: 1px solid var(--line); border-radius: 16px;
    padding: 1rem 1.05rem; min-height: 100%; box-shadow: 0 8px 24px rgba(23, 35, 54, .035);
  }
  .note-card .index { color: var(--coral); font-weight: 900; margin-right: .55rem; }
  .note-card p { margin: 0; line-height: 1.55; }
  .term-chip {
    display: inline-block; margin: 0 .35rem .4rem 0; padding: .35rem .65rem;
    border-radius: 999px; background: var(--forest-soft); color: var(--forest);
    font-size: .82rem; font-weight: 750;
  }
  .confidence {
    display: inline-block; border-radius: 999px; padding: .16rem .48rem;
    background: #f8e6df; color: #973d26; font-size: .72rem; font-weight: 850;
  }
  .prediction { border-left: 3px solid var(--coral); padding-left: .85rem; margin: .2rem 0 1.1rem; }
  .prediction h4 { margin: 0 0 .2rem; color: var(--ink); }
  .prediction p { margin: .35rem 0 0; color: var(--muted); }
  .subtle { color: var(--muted); font-size: .86rem; }

  [data-testid="stMetric"] {
    background: white; border: 1px solid var(--line); border-radius: 15px; padding: .85rem 1rem;
  }
  [data-testid="stTabs"] button[aria-selected="true"] { color: var(--coral); }
  .stButton > button[kind="primary"] { background: var(--forest); border-color: var(--forest); }
  .stDownloadButton > button { border-color: #b8c5c1; }
  [data-testid="stExpander"] { background: white; border-color: var(--line); border-radius: 13px; }

  @media (max-width: 700px) {
    .block-container { padding-top: 1.4rem; }
    .session-banner { align-items: flex-start; }
  }
</style>
"""


DEMO_MATERIAL = """Learning outcomes describe what students should be able to explain, compare, and apply after a study unit. A useful learning outcome uses an observable verb and aligns with both learning activities and assessment. Formative assessment provides feedback during the learning process, while summative assessment evaluates achievement at the end of a unit. Constructive alignment connects learning outcomes, teaching activities, and assessment tasks. When these three elements are consistent, students can focus their effort on the intended knowledge and skills. Feedback is most effective when it is timely, specific, and gives the learner a clear next action. Rubrics make performance criteria visible and can improve self-assessment before an assignment is submitted."""
DEMO_DISCUSSION = "How does constructive alignment improve learning? Compare formative and summative assessment."
DEMO_ASSIGNMENT = "Create one measurable learning outcome and a short rubric that assesses it."


def default_session() -> dict[str, Any]:
    return {
        "title": "",
        "material": "",
        "discussion": "",
        "assignments": "",
        "pack": None,
        "engine": "",
        "generated_at": "",
    }


def init_state() -> None:
    if "study_sessions" not in st.session_state:
        st.session_state.study_sessions = {
            str(number): default_session() for number in range(1, 9)
        }


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        value = ""
    return str(value or os.getenv(name, default))


def initialize_widget_values(session_id: str) -> None:
    data = st.session_state.study_sessions[session_id]
    for field in ("title", "material", "discussion", "assignments"):
        st.session_state.setdefault(f"{field}_{session_id}", data.get(field, ""))


def sync_current_session(session_id: str) -> None:
    data = st.session_state.study_sessions[session_id]
    for field in ("title", "material", "discussion", "assignments"):
        data[field] = st.session_state.get(f"{field}_{session_id}", "")


def reset_widget_values(session_id: str) -> None:
    for field in ("title", "material", "discussion", "assignments"):
        st.session_state.pop(f"{field}_{session_id}", None)


def load_demo(session_id: str) -> None:
    """Populate the current session before Streamlit instantiates its widgets."""

    demo_values = {
        "title": "Constructive alignment",
        "material": DEMO_MATERIAL,
        "discussion": DEMO_DISCUSSION,
        "assignments": DEMO_ASSIGNMENT,
    }
    for field, value in demo_values.items():
        st.session_state[f"{field}_{session_id}"] = value
        st.session_state.study_sessions[session_id][field] = value


def clear_session(session_id: str) -> None:
    """Clear session data before Streamlit instantiates its input widgets."""

    st.session_state.study_sessions[session_id] = default_session()
    for field in ("title", "material", "discussion", "assignments"):
        st.session_state[f"{field}_{session_id}"] = ""


def pack_markdown(session_id: str, data: dict[str, Any]) -> str:
    pack = StudyPack.model_validate(data["pack"])
    title = data.get("title") or f"Session {session_id}"
    lines = [f"# {title}", "", f"Generated with: {data.get('engine', 'Unknown')}", ""]
    lines.extend(["## Summary", *[f"- {item}" for item in pack.summary], ""])
    lines.extend(["## Key terms", ", ".join(pack.key_terms), ""])
    lines.append("## Exam focus")
    lines.extend(
        f"- **{item.topic} ({item.confidence})** — {item.rationale}"
        for item in pack.predictions
    )
    lines.extend(["", "## Flashcards"])
    for card in pack.flashcards:
        lines.extend([f"- **Q:** {card.front}", f"  **A:** {card.back}"])
    lines.extend(["", "## Practice questions"])
    for index, question in enumerate(pack.quiz, start=1):
        lines.append(f"{index}. {question.question}")
        lines.extend(f"   - {chr(65 + option_index)}. {option}" for option_index, option in enumerate(question.options))
        lines.append(f"   - Answer: {chr(65 + question.correct_index)} — {question.explanation}")
    lines.extend(["", "> Exam-focus items are study priorities inferred from your notes, not guaranteed exam content."])
    return "\n".join(lines)


def backup_json() -> str:
    return json.dumps(
        {"version": 1, "sessions": st.session_state.study_sessions},
        ensure_ascii=False,
        indent=2,
    )


def restore_backup(payload: bytes) -> None:
    decoded = json.loads(payload.decode("utf-8"))
    incoming = decoded.get("sessions")
    if not isinstance(incoming, dict):
        raise ValueError("This file does not contain a UT Study Prep session backup.")

    restored: dict[str, dict[str, Any]] = {}
    for number in range(1, 9):
        session_id = str(number)
        item = incoming.get(session_id, default_session())
        clean = default_session()
        for field in clean:
            if field in item:
                clean[field] = item[field]
        if clean["pack"] is not None:
            clean["pack"] = StudyPack.model_validate(clean["pack"]).model_dump()
        restored[session_id] = clean

    st.session_state.study_sessions = restored
    for number in range(1, 9):
        reset_widget_values(str(number))


def render_summary(pack: StudyPack, session_id: str) -> None:
    for index, point in enumerate(pack.summary, start=1):
        st.markdown(
            f'<div class="note-card"><p><span class="index">{index:02}</span>{html.escape(point)}</p></div>',
            unsafe_allow_html=True,
        )
        st.write("")

    if pack.key_terms:
        st.markdown("#### Key terms")
        chips = "".join(
            f'<span class="term-chip">{html.escape(term)}</span>' for term in pack.key_terms
        )
        st.markdown(chips, unsafe_allow_html=True)

    st.markdown("#### Audio reader")
    reader_language = st.selectbox(
        "Reading language",
        options=["id-ID", "en-US"],
        format_func=lambda item: "Bahasa Indonesia" if item == "id-ID" else "English",
        key=f"reader_language_{session_id}",
        label_visibility="collapsed",
    )
    spoken_text = " ".join(pack.summary)
    st.iframe(
        speech_controls(spoken_text, reader_language),
        height=158,
        alt="Audio controls for the generated session summary",
    )


def render_predictions(pack: StudyPack) -> None:
    st.caption("Study priorities inferred from repetition, discussions, and assignment prompts — never a guarantee of exam content.")
    if not pack.predictions:
        st.info("Add discussion questions or assignment prompts to strengthen exam-focus signals.")
        return
    for prediction in pack.predictions:
        st.markdown(
            "<div class='prediction'>"
            f"<h4>{html.escape(prediction.topic)} &nbsp;"
            f"<span class='confidence'>{html.escape(prediction.confidence)}</span></h4>"
            f"<p>{html.escape(prediction.rationale)}</p></div>",
            unsafe_allow_html=True,
        )


def render_flashcards(pack: StudyPack) -> None:
    if not pack.flashcards:
        st.info("No flashcards were generated from this material.")
        return
    st.caption("Try to answer before opening each card.")
    for index, card in enumerate(pack.flashcards, start=1):
        with st.expander(f"{index:02} · {card.front}"):
            st.write(card.back)


def render_quiz(pack: StudyPack, session_id: str) -> None:
    if not pack.quiz:
        st.info("Add more complete sentences to generate a practice quiz.")
        return

    fingerprint = sha256(pack.model_dump_json().encode("utf-8")).hexdigest()[:10]
    result_key = f"quiz_result_{session_id}_{fingerprint}"
    answers: list[int | None] = []
    with st.form(key=f"quiz_form_{session_id}_{fingerprint}"):
        for index, question in enumerate(pack.quiz, start=1):
            st.markdown(f"**{index}. {question.question}**")
            choice = st.radio(
                f"Answer for question {index}",
                options=list(range(len(question.options))),
                format_func=lambda option, q=question: q.options[option],
                index=None,
                key=f"quiz_choice_{session_id}_{fingerprint}_{index}",
                label_visibility="collapsed",
            )
            answers.append(choice)
        submitted = st.form_submit_button("Check my answers", type="primary")

    if submitted:
        st.session_state[result_key] = answers

    saved_answers = st.session_state.get(result_key)
    if saved_answers is None:
        return

    score = sum(
        answer == question.correct_index
        for answer, question in zip(saved_answers, pack.quiz)
    )
    if any(answer is None for answer in saved_answers):
        st.warning(f"Score: {score}/{len(pack.quiz)}. Unanswered questions count as incorrect.")
    else:
        st.success(f"Score: {score}/{len(pack.quiz)}")

    for index, (answer, question) in enumerate(zip(saved_answers, pack.quiz), start=1):
        is_correct = answer == question.correct_index
        icon = "✅" if is_correct else "↗"
        with st.expander(f"{icon} Review question {index}"):
            st.write(f"**Correct answer:** {question.options[question.correct_index]}")
            st.write(question.explanation)


init_state()
st.markdown(APP_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## UT Study Prep")
    st.caption("Your 8-session final-exam workspace")
    selected_number = st.selectbox(
        "Study session",
        options=list(range(1, 9)),
        format_func=lambda number: f"Session {number}",
        key="selected_session",
    )
    session_id = str(selected_number)

    ready_count = sum(bool(item.get("pack")) for item in st.session_state.study_sessions.values())
    st.progress(ready_count / 8, text=f"{ready_count} of 8 sessions prepared")
    st.divider()

    st.markdown("#### Analysis engine")
    engine_choice = st.radio(
        "Choose an engine",
        options=["Auto", "Local", "OpenAI"],
        help="Auto uses OpenAI when a key is available and otherwise uses the local engine.",
        label_visibility="collapsed",
    )

    configured_key = secret("OPENAI_API_KEY")
    if configured_key:
        st.success("OpenAI key found in secrets", icon="✓")
        temporary_key = ""
    else:
        temporary_key = st.text_input(
            "Temporary OpenAI API key",
            type="password",
            help="Used only for this running session. Leave blank to use the free local engine.",
        )
    api_key = configured_key or temporary_key

    with st.expander("AI settings"):
        model = st.text_input("Model", value=secret("OPENAI_MODEL", DEFAULT_MODEL))
        st.caption("OpenAI mode sends the pasted content to the API. Local mode makes no AI-provider call.")

    st.divider()
    upload = st.file_uploader("Restore a study backup", type=["json"])
    if upload is not None and st.button("Restore all sessions", use_container_width=True):
        try:
            restore_backup(upload.getvalue())
            st.success("Backup restored.")
            st.rerun()
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            st.error(f"Could not restore this backup: {exc}")


initialize_widget_values(session_id)
session_data = st.session_state.study_sessions[session_id]

st.markdown('<div class="hero-kicker">FOCUS · RECALL · REPEAT</div>', unsafe_allow_html=True)
st.title("Turn Tuton notes into a study plan.")
st.markdown(
    '<p class="hero-copy">Paste one tutorial session at a time. UT Study Prep turns your own material into a crisp summary, exam-focus signals, active-recall cards, a practice quiz, and a browser audio lesson.</p>',
    unsafe_allow_html=True,
)

prepared_flashcards = sum(
    len((item.get("pack") or {}).get("flashcards", []))
    for item in st.session_state.study_sessions.values()
)
prepared_questions = sum(
    len((item.get("pack") or {}).get("quiz", []))
    for item in st.session_state.study_sessions.values()
)
metric_one, metric_two, metric_three = st.columns(3)
metric_one.metric("Sessions ready", f"{ready_count}/8")
metric_two.metric("Flashcards", prepared_flashcards)
metric_three.metric("Practice questions", prepared_questions)

session_title = session_data.get("title") or "Untitled tutorial"
st.markdown(
    "<div class='session-banner'>"
    f"<div class='session-number'>{selected_number:02}</div>"
    f"<div class='session-banner-copy'><strong>Session {selected_number}</strong>"
    f"<span>{html.escape(session_title)}</span></div>"
    "</div>",
    unsafe_allow_html=True,
)

st.subheader("1. Add your session material")
st.text_input(
    "Session title (optional)",
    placeholder="Example: Learning theories and assessment",
    key=f"title_{session_id}",
)
st.text_area(
    "Tuton material",
    height=250,
    placeholder="Paste tutorial notes, module excerpts, or your own study notes here…",
    key=f"material_{session_id}",
)
input_left, input_right = st.columns(2)
with input_left:
    st.text_area(
        "Discussion questions",
        height=135,
        placeholder="Paste the session's discussion prompts…",
        key=f"discussion_{session_id}",
    )
with input_right:
    st.text_area(
        "Assignments",
        height=135,
        placeholder="Paste task instructions or assignment criteria…",
        key=f"assignments_{session_id}",
    )

sync_current_session(session_id)
session_data = st.session_state.study_sessions[session_id]

button_one, button_two, button_three, button_space = st.columns([1.3, 1, 1, 2])
with button_one:
    generate = st.button("Generate study pack", type="primary", use_container_width=True)
with button_two:
    st.button(
        "Load demo",
        use_container_width=True,
        on_click=load_demo,
        args=(session_id,),
    )
with button_three:
    st.button(
        "Clear session",
        use_container_width=True,
        on_click=clear_session,
        args=(session_id,),
    )

if generate:
    material = session_data["material"].strip()
    discussion = session_data["discussion"].strip()
    assignments = session_data["assignments"].strip()
    combined_length = len(material) + len(discussion) + len(assignments)
    if combined_length < 80:
        st.error("Add at least 80 characters of material before generating your study pack.")
    else:
        chosen_engine = engine_choice
        if chosen_engine == "Auto":
            chosen_engine = "OpenAI" if api_key else "Local"

        try:
            with st.spinner(f"Building Session {selected_number} with {chosen_engine}…"):
                if chosen_engine == "OpenAI":
                    if not api_key:
                        raise ValueError("Add an OpenAI API key in the sidebar, or choose Local.")
                    pack = build_ai_study_pack(
                        session_number=selected_number,
                        material=material,
                        discussion=discussion,
                        assignments=assignments,
                        api_key=api_key,
                        model=model.strip() or DEFAULT_MODEL,
                    )
                    engine_label = f"OpenAI · {model.strip() or DEFAULT_MODEL}"
                else:
                    pack = build_local_study_pack(material, discussion, assignments)
                    engine_label = "Local study engine"

            session_data["pack"] = pack.model_dump()
            session_data["engine"] = engine_label
            session_data["generated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
            st.toast("Study pack ready", icon="✓")
            st.rerun()
        except Exception as exc:  # Streamlit should surface service errors without crashing the session.
            st.error(f"Could not generate this study pack: {exc}")
            if chosen_engine == "OpenAI":
                st.info("Your pasted text is still here. Choose Local to continue without an API call.")


session_data = st.session_state.study_sessions[session_id]
if session_data.get("pack"):
    pack = StudyPack.model_validate(session_data["pack"])
    st.subheader("2. Review your study pack")
    st.caption(
        f"Generated with {session_data.get('engine', 'study engine')} · "
        f"{session_data.get('generated_at', '')}"
    )

    summary_tab, predictions_tab, cards_tab, quiz_tab = st.tabs(
        ["Summary & audio", "Exam focus", "Flashcards", "Practice quiz"]
    )
    with summary_tab:
        render_summary(pack, session_id)
    with predictions_tab:
        render_predictions(pack)
    with cards_tab:
        render_flashcards(pack)
    with quiz_tab:
        render_quiz(pack, session_id)

    st.divider()
    download_one, download_two, _ = st.columns([1.3, 1.25, 2])
    with download_one:
        st.download_button(
            "Download this study pack",
            data=pack_markdown(session_id, session_data),
            file_name=f"ut-study-prep-session-{session_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with download_two:
        st.download_button(
            "Back up all 8 sessions",
            data=backup_json(),
            file_name="ut-study-prep-backup.json",
            mime="application/json",
            use_container_width=True,
        )
else:
    st.info("Your generated summary, exam focus, flashcards, quiz, and audio controls will appear here.")

st.markdown("<div class='hero-rule'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='subtle'>UT Study Prep supports revision; it does not guarantee or reproduce final-exam questions. Verify important facts against your official module materials.</p>",
    unsafe_allow_html=True,
)
