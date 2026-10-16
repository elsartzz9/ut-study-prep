"""UT Study Prep — a lightweight Streamlit companion for final-exam revision."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import html
import json
import os
import random
import re
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, model_validator
import streamlit as st

st.set_page_config(
    page_title="UT Study Prep",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Typed study-pack models
# -----------------------------------------------------------------------------


class Prediction(BaseModel):
    """A study priority inferred from the learner's own material."""

    topic: str = Field(min_length=2, max_length=140)
    rationale: str = Field(min_length=4, max_length=500)
    confidence: Literal["High", "Medium", "Low"]


class Flashcard(BaseModel):
    """A prompt and answer pair for active recall."""

    front: str = Field(min_length=2, max_length=240)
    back: str = Field(min_length=2, max_length=800)


class QuizQuestion(BaseModel):
    """A multiple-choice question with a zero-based answer index."""

    question: str = Field(min_length=4, max_length=500)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=2, max_length=800)

    @model_validator(mode="after")
    def answer_must_exist(self) -> "QuizQuestion":
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index must point to an available option")
        return self


class StudyPack(BaseModel):
    """Everything produced for one tutorial session."""

    summary: list[str] = Field(min_length=1, max_length=8)
    key_terms: list[str] = Field(default_factory=list, max_length=12)
    predictions: list[Prediction] = Field(default_factory=list, max_length=6)
    flashcards: list[Flashcard] = Field(default_factory=list, max_length=10)
    quiz: list[QuizQuestion] = Field(default_factory=list, max_length=8)


# -----------------------------------------------------------------------------
# Dependency-light local study engine (previously analysis.py)
# -----------------------------------------------------------------------------


STOP_WORDS = {
    # English
    "about", "after", "again", "against", "also", "among", "and", "are",
    "because", "been", "before", "being", "between", "both", "but", "can",
    "could", "does", "each", "from", "have", "into", "more", "most", "not",
    "only", "other", "our", "should", "some", "such", "than", "that", "the",
    "their", "then", "there", "these", "they", "this", "those", "through",
    "under", "using", "very", "was", "were", "what", "when", "where", "which",
    "while", "will", "with", "would", "your",
    # Indonesian
    "adalah", "agar", "akan", "anda", "antara", "atau", "bagi", "bahwa",
    "banyak", "beberapa", "berikut", "dalam", "dapat", "dari", "dengan", "dia",
    "digunakan", "hal", "harus", "hingga", "ini", "itu", "jadi", "jika", "juga",
    "karena", "ke", "kemudian", "kepada", "lebih", "melalui", "memiliki", "menjadi",
    "merupakan", "oleh", "pada", "para", "saat", "saling", "sebagai", "sebuah",
    "secara", "setelah", "setiap", "sudah", "terdapat", "terhadap", "tersebut",
    "tetapi", "tidak", "untuk", "yang",
}

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{2,}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _clean_sentence(value: str) -> str:
    value = re.sub(r"^[\s\-–—•*\d.)]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def split_sentences(text: str) -> list[str]:
    """Return readable, de-duplicated sentences from pasted tutorial content."""

    sentences: list[str] = []
    seen: set[str] = set()
    for piece in SENTENCE_SPLIT_RE.split(text.replace("\r", "\n")):
        sentence = _clean_sentence(piece)
        fingerprint = sentence.casefold()
        if 28 <= len(sentence) <= 700 and fingerprint not in seen:
            sentences.append(sentence)
            seen.add(fingerprint)
    return sentences


def _tokens(text: str) -> list[str]:
    return [
        token.casefold()
        for token in TOKEN_RE.findall(text)
        if token.casefold() not in STOP_WORDS and not token.isdigit()
    ]


def extract_keywords(text: str, limit: int = 10) -> list[str]:
    """Extract frequent concepts while preserving a natural display form."""

    tokens = _tokens(text)
    counts = Counter(tokens)
    first_form: dict[str, str] = {}
    for token in TOKEN_RE.findall(text):
        lowered = token.casefold()
        if lowered not in STOP_WORDS:
            first_form.setdefault(lowered, token)

    ranked = sorted(counts, key=lambda item: (-counts[item], tokens.index(item)))
    return [first_form.get(item, item).strip("_- ") for item in ranked[:limit]]


def _rank_sentences(sentences: list[str], keywords: list[str]) -> list[str]:
    weights = {term.casefold(): len(keywords) - index for index, term in enumerate(keywords)}
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = _tokens(sentence)
        if not sentence_tokens:
            continue
        score = sum(weights.get(token, 0) for token in set(sentence_tokens))
        score /= max(len(sentence_tokens) ** 0.55, 1)
        if 45 <= len(sentence) <= 260:
            score += 1.5
        scored.append((score, index, sentence))
    return [item[2] for item in sorted(scored, key=lambda item: (-item[0], item[1]))]


def _sentence_for_term(term: str, sentences: list[str]) -> str:
    match = term.casefold()
    for sentence in sentences:
        if match in sentence.casefold():
            return sentence
    return sentences[0] if sentences else f"Review how {term} is defined and applied."


def _prediction_terms(
    material_keywords: list[str], discussion: str, assignments: str
) -> list[tuple[str, str, str]]:
    assessment_text = f"{discussion}\n{assignments}".strip()
    assessment_keywords = extract_keywords(assessment_text, limit=8)
    material_set = {item.casefold() for item in material_keywords}

    predictions: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for term in assessment_keywords:
        lowered = term.casefold()
        if lowered in used:
            continue
        confidence = "High" if lowered in material_set else "Medium"
        rationale = (
            "Appears in the tutorial material and is reinforced by a discussion or assignment prompt."
            if confidence == "High"
            else "Appears in a discussion or assignment prompt, so it is worth practicing as an applied concept."
        )
        predictions.append((term, rationale, confidence))
        used.add(lowered)
        if len(predictions) == 4:
            return predictions

    for term in material_keywords:
        lowered = term.casefold()
        if lowered not in used:
            predictions.append(
                (
                    term,
                    "Repeated in the session material, which makes it a strong candidate for definition, comparison, or application questions.",
                    "Medium",
                )
            )
            used.add(lowered)
        if len(predictions) == 4:
            break
    return predictions


def _make_quiz(
    keywords: list[str], ranked_sentences: list[str], seed_text: str, limit: int = 5
) -> list[QuizQuestion]:
    if len(ranked_sentences) < 2:
        return []

    seed = int(sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    quiz: list[QuizQuestion] = []
    for term in keywords[:limit]:
        correct = _sentence_for_term(term, ranked_sentences)
        distractor_pool = [item for item in ranked_sentences if item != correct]
        if not distractor_pool:
            continue
        distractors = distractor_pool[:3]
        while len(distractors) < 3:
            distractors.append(
                f"The material does not connect {term} to any broader principle or example."
            )
        options = [correct, *distractors[:3]]
        rng.shuffle(options)
        quiz.append(
            QuizQuestion(
                question=f"Which statement best matches the material's treatment of “{term}”?",
                options=options,
                correct_index=options.index(correct),
                explanation=f"The best answer is the statement taken directly from the session notes about {term}.",
            )
        )
    return quiz


def build_local_study_pack(
    material: str,
    discussion: str = "",
    assignments: str = "",
) -> StudyPack:
    """Create an extractive study pack without an external AI service."""

    combined = "\n".join(part for part in (material, discussion, assignments) if part.strip())
    if len(combined.strip()) < 80:
        raise ValueError("Add at least 80 characters of study material before generating a study pack.")

    material_sentences = split_sentences(material)
    all_sentences = split_sentences(combined)
    if not all_sentences:
        raise ValueError("The material needs a few complete sentences so it can be analyzed.")

    keywords = extract_keywords(combined, limit=10)
    ranked = _rank_sentences(material_sentences or all_sentences, keywords)
    summary = ranked[:5] or all_sentences[:5]
    predictions = [
        Prediction(topic=topic, rationale=rationale, confidence=confidence)
        for topic, rationale, confidence in _prediction_terms(keywords, discussion, assignments)
    ]
    flashcards = [
        Flashcard(
            front=f"Explain {term} in the context of this session.",
            back=_sentence_for_term(term, ranked or all_sentences),
        )
        for term in keywords[:6]
    ]
    return StudyPack(
        summary=summary,
        key_terms=keywords,
        predictions=predictions,
        flashcards=flashcards,
        quiz=_make_quiz(keywords, ranked or all_sentences, combined),
    )


# -----------------------------------------------------------------------------
# Optional OpenAI study engine (previously ai.py)
# -----------------------------------------------------------------------------


DEFAULT_MODEL = "gpt-6-luna"


def build_ai_study_pack(
    *,
    session_number: int,
    material: str,
    discussion: str,
    assignments: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> StudyPack:
    """Generate a schema-validated study pack with the Responses API."""

    if not api_key:
        raise ValueError("An OpenAI API key is required for OpenAI mode.")

    client = OpenAI(api_key=api_key)
    source = f"""
SESSION: {session_number}

TUTON MATERIAL:
{material[:45_000]}

DISCUSSION QUESTIONS:
{discussion[:8_000] or "Not provided"}

ASSIGNMENTS:
{assignments[:8_000] or "Not provided"}
""".strip()

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You create accurate university exam-preparation material from the learner's "
                    "own notes. Match the dominant language of the source. Return 4-6 concise summary "
                    "points, 5-8 key terms, 3-4 exam-focus predictions, 5-6 flashcards, and 5 "
                    "multiple-choice questions. Every quiz question needs 4 plausible options. Base "
                    "all factual claims on the supplied source. Predictions are study priorities, not "
                    "claims about leaked or guaranteed exam content. Use High confidence only when a "
                    "concept is repeated in the material and reinforced by a discussion or assignment."
                ),
            },
            {"role": "user", "content": source},
        ],
        text_format=StudyPack,
        max_output_tokens=5_000,
    )

    if response.output_parsed is None:
        raise RuntimeError("The AI response did not contain a usable study pack.")
    return response.output_parsed


# -----------------------------------------------------------------------------
# Browser Text-to-Speech (previously tts.py)
# -----------------------------------------------------------------------------


def speech_controls(summary_text: str, language: str = "id-ID") -> str:
    """Return a self-contained Web Speech API player."""

    safe_text = json.dumps(summary_text, ensure_ascii=False).replace("</", "<\\/")
    safe_language = json.dumps(language)
    if not summary_text.strip():
        return '<div class="empty">Generate a summary first, then press Listen.</div>'

    return f"""
    <div class="reader" role="group" aria-label="Summary audio reader">
      <div class="reader-head">
        <div><span class="eyebrow">AUDIO READER</span><strong>Listen to this summary</strong></div>
        <select id="voice" aria-label="Choose a browser voice"></select>
      </div>
      <div class="controls">
        <button id="play" type="button">▶ Listen</button>
        <button id="pause" type="button">Ⅱ Pause / resume</button>
        <button id="stop" type="button">■ Stop</button>
      </div>
      <p id="status" aria-live="polite">Uses the voices already available in your browser.</p>
    </div>
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #172336; }}
      .reader {{ border: 1px solid #dfe4e2; border-radius: 16px; padding: 16px; background: #fffdf8; }}
      .reader-head {{ display: flex; gap: 12px; justify-content: space-between; align-items: center; }}
      .reader-head div {{ display: grid; gap: 3px; }}
      .eyebrow {{ color: #d45c3b; font-size: 10px; font-weight: 800; letter-spacing: .14em; }}
      strong {{ font-size: 16px; }}
      select {{ max-width: 48%; border: 1px solid #ccd4d1; border-radius: 9px; padding: 8px; background: white; }}
      .controls {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
      button {{ border: 0; border-radius: 9px; padding: 9px 13px; font-weight: 750; cursor: pointer; }}
      #play {{ color: white; background: #123d3a; }}
      #pause, #stop {{ color: #123d3a; background: #e8efec; }}
      p {{ margin: 10px 0 0; color: #65716f; font-size: 12px; }}
    </style>
    <script>
      const text = {safe_text};
      const language = {safe_language};
      const synth = window.speechSynthesis;
      const voiceSelect = document.getElementById('voice');
      const status = document.getElementById('status');

      function loadVoices() {{
        const voices = synth.getVoices();
        voiceSelect.innerHTML = '';
        voices.forEach((voice, index) => {{
          const option = document.createElement('option');
          option.value = String(index);
          option.textContent = `${{voice.name}} (${{voice.lang}})`;
          if (voice.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase())) option.selected = true;
          voiceSelect.appendChild(option);
        }});
      }}

      loadVoices();
      if ('onvoiceschanged' in synth) synth.onvoiceschanged = loadVoices;
      document.getElementById('play').addEventListener('click', () => {{
        synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = language;
        const selected = synth.getVoices()[Number(voiceSelect.value)];
        if (selected) utterance.voice = selected;
        utterance.rate = 0.96;
        utterance.onstart = () => status.textContent = 'Reading the summary…';
        utterance.onend = () => status.textContent = 'Finished. Replay whenever you are ready.';
        utterance.onerror = () => status.textContent = 'This browser could not start speech. Try another voice.';
        synth.speak(utterance);
      }});
      document.getElementById('pause').addEventListener('click', () => {{
        if (synth.paused) {{ synth.resume(); status.textContent = 'Reading the summary…'; }}
        else {{ synth.pause(); status.textContent = 'Paused.'; }}
      }});
      document.getElementById('stop').addEventListener('click', () => {{
        synth.cancel();
        status.textContent = 'Stopped.';
      }});
    </script>
    """


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


# -----------------------------------------------------------------------------
# Master Catalog — UT S1 Sistem Informasi, curriculum 2025/2026
# 51 numbered curriculum slots, 145 SKS, arranged across eight semesters.
# Choice slots preserve every alternative from the official catalog.
# -----------------------------------------------------------------------------


CURRICULUM_SOURCE_URL = (
    "https://www.ut.ac.id/wp-content/uploads/2025/12/"
    "01-Katalog-Kurikulum-FEB-FHISIP-FKIP-Non-PGSD-Non-PGPAUD-dan-Non-PAI-"
    "FST-UT-2025-2026-10Desember2025.pdf"
)

COURSE_CATALOG: list[dict[str, Any]] = [
    {"slot": 1, "semester": 1, "code": "STSI4101", "name": "Pengantar Sistem Informasi", "sks": 3},
    {"slot": 2, "semester": 1, "code": "STSI4103", "name": "Sistem Operasi", "sks": 3},
    {
        "slot": 3,
        "semester": 1,
        "code": "MKWN4101/02/03/04/05/07",
        "name": "Pendidikan Agama — pilih sesuai data pribadi",
        "sks": 3,
        "choices": [
            "MKWN4101 — Pendidikan Agama Islam",
            "MKWN4102 — Pendidikan Agama Katolik",
            "MKWN4103 — Pendidikan Agama Kristen",
            "MKWN4104 — Pendidikan Agama Buddha",
            "MKWN4105 — Pendidikan Agama Hindu",
            "MKWN4107 — Pendidikan Agama Konghucu",
        ],
    },
    {"slot": 4, "semester": 1, "code": "STSI4102", "name": "Algoritma dan Pemrograman", "sks": 3},
    {"slot": 5, "semester": 1, "code": "STMA4112", "name": "Matematika Dasar", "sks": 3},
    {"slot": 6, "semester": 1, "code": "MKWN4109", "name": "Pendidikan Kewarganegaraan", "sks": 2},
    {"slot": 7, "semester": 2, "code": "STSI4105", "name": "Basis Data", "sks": 3},
    {"slot": 8, "semester": 2, "code": "STSI4104", "name": "Struktur Data", "sks": 3},
    {"slot": 9, "semester": 2, "code": "MKKI4201", "name": "Pengantar Statistika", "sks": 3},
    {"slot": 10, "semester": 2, "code": "MKDI4201", "name": "Bahasa Inggris", "sks": 3},
    {"slot": 11, "semester": 2, "code": "MKWN4108", "name": "Bahasa Indonesia", "sks": 2},
    {"slot": 12, "semester": 2, "code": "MKWN4110", "name": "Pancasila", "sks": 2},
    {"slot": 13, "semester": 2, "code": "STMA4113", "name": "Aljabar Linear Elementer", "sks": 2},
    {"slot": 14, "semester": 3, "code": "STIK4111", "name": "Dasar Pemrograman R", "sks": 3},
    {"slot": 15, "semester": 3, "code": "STSI4106", "name": "Logika Informatika", "sks": 3},
    {"slot": 16, "semester": 3, "code": "STSI4201", "name": "Pemrograman Berbasis Desktop", "sks": 3},
    {"slot": 17, "semester": 3, "code": "STSI4203", "name": "Interaksi Manusia dan Komputer", "sks": 3},
    {"slot": 18, "semester": 3, "code": "STSI4202", "name": "Rekayasa Perangkat Lunak", "sks": 3},
    {"slot": 19, "semester": 3, "code": "STSI4205", "name": "Jaringan Komputer", "sks": 3},
    {"slot": 20, "semester": 3, "code": "MKDI4202", "name": "Belajar di Era Digital", "sks": 3},
    {"slot": 21, "semester": 4, "code": "MKDI4203", "name": "Kewirausahaan di Era Digital", "sks": 3},
    {"slot": 22, "semester": 4, "code": "STSI4204", "name": "Analisis dan Visualisasi Data", "sks": 2},
    {"slot": 23, "semester": 4, "code": "STSI4208", "name": "Analisis dan Perancangan Sistem", "sks": 3},
    {"slot": 24, "semester": 4, "code": "STSI4209", "name": "Pemrograman Berbasis Web", "sks": 3},
    {"slot": 25, "semester": 4, "code": "STSI4206", "name": "Proses Bisnis", "sks": 2},
    {"slot": 26, "semester": 4, "code": "STSI4207", "name": "Sistem Informasi Manajemen", "sks": 3},
    {"slot": 27, "semester": 4, "code": "EMBS4207", "name": "Perilaku Organisasi", "sks": 3},
    {"slot": 28, "semester": 5, "code": "FSSI4101", "name": "Basic Reading", "sks": 3},
    {"slot": 29, "semester": 5, "code": "STMA4111", "name": "Kalkulus Diferensial", "sks": 3},
    {"slot": 30, "semester": 5, "code": "EMBS4102", "name": "Pengantar Bisnis", "sks": 3},
    {
        "slot": 31,
        "semester": 5,
        "code": "STSI4301 / STSI4302",
        "name": "Mata kuliah pilihan I",
        "sks": 3,
        "choices": [
            "STSI4301 — Sistem Pendukung Keputusan",
            "STSI4302 — Administrasi Server",
        ],
    },
    {"slot": 32, "semester": 5, "code": "FSAP4102", "name": "Teori Organisasi", "sks": 3},
    {"slot": 33, "semester": 5, "code": "STSI4303", "name": "Pemrograman Berbasis Perangkat Bergerak", "sks": 3},
    {"slot": 34, "semester": 5, "code": "STSI4308", "name": "Komunikasi Bisnis dan Teknis", "sks": 2},
    {
        "slot": 35,
        "semester": 6,
        "code": "STSI4307 / STSI4309",
        "name": "Mata kuliah pilihan II",
        "sks": 3,
        "choices": ["STSI4307 — Data Mining", "STSI4309 — Administrasi Jaringan"],
    },
    {"slot": 36, "semester": 6, "code": "STSI4306", "name": "Arsitektur dan Perancangan Sistem Enterprise", "sks": 3},
    {"slot": 37, "semester": 6, "code": "STSI4305", "name": "Etika Profesi", "sks": 2},
    {
        "slot": 38,
        "semester": 6,
        "code": "STPL4211 / MKKI4301",
        "name": "Mata kuliah pilihan III",
        "sks": 3,
        "choices": [
            "STPL4211 — Sistem Informasi Perencanaan",
            "MKKI4301 — Pemberdayaan Masyarakat",
        ],
    },
    {"slot": 39, "semester": 6, "code": "STSI4304", "name": "Dasar Infrastruktur TI", "sks": 2},
    {"slot": 40, "semester": 6, "code": "STSI4310", "name": "Metodologi Penelitian", "sks": 3},
    {"slot": 41, "semester": 6, "code": "EMBS4101", "name": "Manajemen", "sks": 4},
    {
        "slot": 42,
        "semester": 7,
        "code": "STSI4409 / STSI4404",
        "name": "Mata kuliah pilihan IV",
        "sks": 3,
        "choices": ["STSI4409 — Data Warehouse", "STSI4404 — Keamanan Jaringan"],
    },
    {"slot": 43, "semester": 7, "code": "STDA4101", "name": "Pengantar Sains Data", "sks": 3},
    {"slot": 44, "semester": 7, "code": "STSI4403", "name": "Manajemen Risiko dan Audit Sistem Informasi", "sks": 3},
    {"slot": 45, "semester": 7, "code": "STSI4402", "name": "Tata Kelola Teknologi Informasi", "sks": 2},
    {"slot": 46, "semester": 7, "code": "STSI4440", "name": "Capstone Project", "sks": 6},
    {"slot": 47, "semester": 8, "code": "STSI4406", "name": "Manajemen Proyek Sistem Informasi", "sks": 2},
    {"slot": 48, "semester": 8, "code": "STSI4405", "name": "Keamanan Sistem Informasi", "sks": 2},
    {"slot": 49, "semester": 8, "code": "STSI4407", "name": "Manajemen Layanan Teknologi Informasi", "sks": 3},
    {"slot": 50, "semester": 8, "code": "STSI4408", "name": "E-Bisnis", "sks": 3},
    {"slot": 51, "semester": 8, "code": "EACC4207", "name": "Sistem Informasi Akuntansi", "sks": 3},
]


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


def validate_course_catalog() -> None:
    """Fail fast if the embedded curriculum is edited inconsistently."""

    expected_semester_sks = {1: 17, 2: 18, 3: 21, 4: 19, 5: 20, 6: 20, 7: 17, 8: 13}
    actual_semester_sks = {
        semester: sum(item["sks"] for item in COURSE_CATALOG if item["semester"] == semester)
        for semester in range(1, 9)
    }
    if len(COURSE_CATALOG) != 51:
        raise ValueError("COURSE_CATALOG must contain exactly 51 numbered curriculum slots.")
    if [item["slot"] for item in COURSE_CATALOG] != list(range(1, 52)):
        raise ValueError("COURSE_CATALOG slots must run consecutively from 1 through 51.")
    if sum(item["sks"] for item in COURSE_CATALOG) != 145:
        raise ValueError("COURSE_CATALOG must total 145 SKS.")
    if actual_semester_sks != expected_semester_sks:
        raise ValueError("COURSE_CATALOG semester totals do not match the official curriculum.")


def render_course_catalog() -> None:
    """Render the embedded 51-slot UT Information Systems curriculum."""

    st.markdown('<div class="hero-kicker">OFFICIAL CURRICULUM · 2025/2026</div>', unsafe_allow_html=True)
    st.title("Master Catalog: S1 Sistem Informasi")
    st.markdown(
        '<p class="hero-copy">Explore all 51 numbered curriculum slots in UT’s current Information Systems program. Choice groups preserve every official alternative while counting once toward the 145-SKS degree total.</p>',
        unsafe_allow_html=True,
    )

    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Curriculum slots", 51)
    metric_two.metric("Total credits", "145 SKS")
    metric_three.metric("Study plan", "8 semesters")

    filter_one, filter_two = st.columns([1.35, 1])
    with filter_one:
        query = st.text_input(
            "Search catalog",
            placeholder="Search by code or course name…",
            key="catalog_search",
        ).strip().casefold()
    with filter_two:
        semester_filter = st.selectbox(
            "Semester",
            options=[0, *range(1, 9)],
            format_func=lambda value: "All semesters" if value == 0 else f"Semester {value}",
            key="catalog_semester",
        )

    filtered = []
    for item in COURSE_CATALOG:
        choice_text = " ".join(item.get("choices", []))
        searchable = f"{item['code']} {item['name']} {choice_text}".casefold()
        if query and query not in searchable:
            continue
        if semester_filter and item["semester"] != semester_filter:
            continue
        filtered.append(item)

    st.caption(f"Showing {len(filtered)} of {len(COURSE_CATALOG)} curriculum slots")
    rows = [
        {
            "No.": item["slot"],
            "Semester": item["semester"],
            "Code": item["code"],
            "Course": item["name"],
            "SKS": item["sks"],
            "Type": "Choose one" if item.get("choices") else "Required",
        }
        for item in filtered
    ]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "No.": st.column_config.NumberColumn(width="small"),
            "Semester": st.column_config.NumberColumn(width="small"),
            "SKS": st.column_config.NumberColumn(width="small"),
        },
    )

    choice_items = [item for item in filtered if item.get("choices")]
    if choice_items:
        st.markdown("### Choice details")
        for item in choice_items:
            with st.expander(f"Slot {item['slot']} · {item['name']}"):
                for choice in item["choices"]:
                    st.markdown(f"- {choice}")

    st.info(
        "Catalog note: the official table numbers choice groups as single curriculum slots. "
        "Select one alternative in each applicable slot. Always confirm registration rules in MyUT."
    )
    st.link_button("Open the official UT curriculum PDF", CURRICULUM_SOURCE_URL)


validate_course_catalog()


init_state()
st.markdown(APP_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## UT Study Prep")
    st.caption("Your 8-session final-exam workspace")
    workspace = st.radio(
        "Workspace",
        options=["Study desk", "Course catalog"],
        horizontal=True,
    )

if workspace == "Course catalog":
    render_course_catalog()
    st.stop()

with st.sidebar:
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
    if upload is not None and st.button("Restore all sessions", width="stretch"):
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
    generate = st.button("Generate study pack", type="primary", width="stretch")
with button_two:
    st.button(
        "Load demo",
        width="stretch",
        on_click=load_demo,
        args=(session_id,),
    )
with button_three:
    st.button(
        "Clear session",
        width="stretch",
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
            width="stretch",
        )
    with download_two:
        st.download_button(
            "Back up all 8 sessions",
            data=backup_json(),
            file_name="ut-study-prep-backup.json",
            mime="application/json",
            width="stretch",
        )
else:
    st.info("Your generated summary, exam focus, flashcards, quiz, and audio controls will appear here.")

st.markdown("<div class='hero-rule'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='subtle'>UT Study Prep supports revision; it does not guarantee or reproduce final-exam questions. Verify important facts against your official module materials.</p>",
    unsafe_allow_html=True,
)
