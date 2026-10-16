from __future__ import annotations

import html
import base64
import json
import math
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="UT Study Prep",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Non-SIPAS master catalog
# -----------------------------------------------------------------------------

CATALOG_MK_UT = [
    {"code": "STSI4101", "name": "Introduction to Information Systems", "credits": 3},
    {"code": "STSI4103", "name": "Operating Systems", "credits": 3},
    {"code": "MKWN4101", "name": "Islamic Religious Education", "credits": 3},
    {"code": "MKWN4102", "name": "Catholic Religious Education", "credits": 3},
    {"code": "MKWN4103", "name": "Christian Religious Education", "credits": 3},
    {"code": "MKWN4104", "name": "Buddhist Religious Education", "credits": 3},
    {"code": "MKWN4105", "name": "Hindu Religious Education", "credits": 3},
    {"code": "MKWN4107", "name": "Confucian Religious Education", "credits": 3},
    {"code": "STSI4102", "name": "Algorithms and Programming", "credits": 3},
    {"code": "STMA4112", "name": "Basic Mathematics", "credits": 3},
    {"code": "MKWN4109", "name": "Civic Education", "credits": 2},
    {"code": "STSI4105", "name": "Databases", "credits": 3},
    {"code": "STSI4104", "name": "Data Structures", "credits": 3},
    {"code": "MKKI4201", "name": "Introduction to Statistics", "credits": 3},
    {"code": "MKDI4201", "name": "English", "credits": 3},
    {"code": "MKWN4108", "name": "Indonesian Language", "credits": 2},
    {"code": "MKWN4110", "name": "Pancasila", "credits": 2},
    {"code": "STMA4113", "name": "Elementary Linear Algebra", "credits": 2},
    {"code": "STIK4111", "name": "Fundamentals of R Programming", "credits": 3},
    {"code": "STSI4106", "name": "Informatics Logic", "credits": 3},
    {"code": "STSI4201", "name": "Desktop-Based Programming", "credits": 3},
    {"code": "STSI4203", "name": "Human-Computer Interaction", "credits": 3},
    {"code": "STSI4202", "name": "Software Engineering", "credits": 3},
    {"code": "STSI4205", "name": "Computer Networks", "credits": 3},
    {"code": "MKDI4202", "name": "Learning in the Digital Era", "credits": 3},
    {"code": "MKDI4203", "name": "Entrepreneurship in the Digital Era", "credits": 3},
    {"code": "STSI4204", "name": "Data Analysis and Visualization", "credits": 2},
    {"code": "STSI4208", "name": "Systems Analysis and Design", "credits": 3},
    {"code": "STSI4209", "name": "Web-Based Programming", "credits": 3},
    {"code": "STSI4206", "name": "Business Processes", "credits": 2},
    {"code": "STSI4207", "name": "Management Information Systems", "credits": 3},
    {"code": "EMBS4207", "name": "Organizational Behavior", "credits": 3},
    {"code": "FSSI4101", "name": "Basic Reading", "credits": 3},
    {"code": "STMA4111", "name": "Differential Calculus", "credits": 3},
    {"code": "EMBS4102", "name": "Introduction to Business", "credits": 3},
    {"code": "STSI4301", "name": "Decision Support Systems", "credits": 3},
    {"code": "STSI4302", "name": "Server Administration", "credits": 3},
    {"code": "FSAP4102", "name": "Organizational Theory", "credits": 3},
    {"code": "STSI4303", "name": "Mobile-Based Programming", "credits": 3},
    {"code": "STSI4308", "name": "Business and Technical Communication", "credits": 2},
    {"code": "STSI4307", "name": "Data Mining", "credits": 3},
    {"code": "STSI4309", "name": "Network Administration", "credits": 3},
    {"code": "STSI4306", "name": "Enterprise System Architecture and Design", "credits": 3},
    {"code": "STSI4305", "name": "Professional Ethics", "credits": 2},
    {"code": "STPL4211", "name": "Planning Information Systems", "credits": 3},
    {"code": "MKKI4301", "name": "Community Empowerment", "credits": 3},
    {"code": "STSI4304", "name": "Fundamentals of IT Infrastructure", "credits": 2},
    {"code": "STSI4310", "name": "Research Methodology", "credits": 3},
    {"code": "EMBS4101", "name": "Management", "credits": 4},
    {"code": "STSI4409", "name": "Data Warehouse", "credits": 3},
    {"code": "STSI4404", "name": "Network Security", "credits": 3},
    {"code": "STDA4101", "name": "Introduction to Data Science", "credits": 3},
    {"code": "STSI4403", "name": "Risk Management and Information Systems Audit", "credits": 3},
    {"code": "STSI4402", "name": "Information Technology Governance", "credits": 2},
    {"code": "STSI4440", "name": "Capstone Project (TAPS)", "credits": 6},
    {"code": "STSI4406", "name": "Information Systems Project Management", "credits": 2},
    {"code": "STSI4405", "name": "Information Systems Security", "credits": 2},
    {"code": "STSI4407", "name": "Information Technology Service Management", "credits": 3},
    {"code": "STSI4408", "name": "E-Business", "credits": 3},
    {"code": "EACC4207", "name": "Accounting Information Systems", "credits": 3},
]

CATALOG_BY_CODE = {course["code"]: course for course in CATALOG_MK_UT}


def validate_catalog() -> None:
    codes = [course["code"] for course in CATALOG_MK_UT]
    if len(CATALOG_MK_UT) != 60:
        raise RuntimeError("The Non-SIPAS master catalog must contain 60 course offerings.")
    if len(codes) != len(set(codes)):
        raise RuntimeError("Duplicate course codes were found in the master catalog.")
    if any(not 1 <= int(course["credits"]) <= 6 for course in CATALOG_MK_UT):
        raise RuntimeError("Every catalog course must contain between 1 and 6 SKS.")


validate_catalog()


# -----------------------------------------------------------------------------
# Persistent SQLite storage
# -----------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("UT_STUDY_DB_PATH", str(APP_DIR / "ut_study_prep.db")))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS semester_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 24),
                is_custom INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                material TEXT NOT NULL DEFAULT '',
                discussion TEXT NOT NULL DEFAULT '',
                assignments TEXT NOT NULL DEFAULT '',
                study_pack_json TEXT,
                provider TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (semester_id, code),
                FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            );
            """
        )
        connection.execute("PRAGMA journal_mode = WAL")
        existing = connection.execute("SELECT id FROM semesters LIMIT 1").fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                ("Semester 1", utc_now()),
            )


def list_semesters() -> list[dict[str, Any]]:
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at FROM semesters ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def create_semester(name: str) -> int:
    clean_name = re.sub(r"\s+", " ", name.strip())
    if not clean_name:
        raise ValueError("Enter a semester name.")
    with connect_db() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                (clean_name, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("That semester already exists.") from exc
    return int(cursor.lastrowid)


def list_semester_courses(
    semester_id: int, *, active_only: bool = True
) -> list[dict[str, Any]]:
    condition = "AND active = 1" if active_only else ""
    with connect_db() as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM semester_courses
            WHERE semester_id = ? {condition}
            ORDER BY is_custom, code
            """,
            (semester_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def sync_catalog_selection(semester_id: int, selected_codes: list[str]) -> None:
    selected = {code for code in selected_codes if code in CATALOG_BY_CODE}
    with connect_db() as connection:
        connection.execute(
            "UPDATE semester_courses SET active = 0, updated_at = ? "
            "WHERE semester_id = ? AND is_custom = 0",
            (utc_now(), semester_id),
        )
        for code in sorted(selected):
            course = CATALOG_BY_CODE[code]
            connection.execute(
                """
                INSERT INTO semester_courses
                    (semester_id, code, name, credits, is_custom, active, updated_at)
                VALUES (?, ?, ?, ?, 0, 1, ?)
                ON CONFLICT(semester_id, code) DO UPDATE SET
                    name = excluded.name,
                    credits = excluded.credits,
                    active = 1,
                    updated_at = excluded.updated_at
                """,
                (semester_id, code, course["name"], course["credits"], utc_now()),
            )


def add_custom_course(semester_id: int, code: str, name: str, credits: int) -> None:
    clean_code = re.sub(r"[^A-Z0-9_-]", "", code.upper().strip())
    clean_name = re.sub(r"\s+", " ", name.strip())
    if not clean_code or not clean_name:
        raise ValueError("A custom course needs both a code and a name.")
    if clean_code in CATALOG_BY_CODE:
        raise ValueError("That code is already in the master catalog. Select it above instead.")
    with connect_db() as connection:
        connection.execute(
            """
            INSERT INTO semester_courses
                (semester_id, code, name, credits, is_custom, active, updated_at)
            VALUES (?, ?, ?, ?, 1, 1, ?)
            ON CONFLICT(semester_id, code) DO UPDATE SET
                name = excluded.name,
                credits = excluded.credits,
                is_custom = 1,
                active = 1,
                updated_at = excluded.updated_at
            """,
            (semester_id, clean_code, clean_name, int(credits), utc_now()),
        )


def remove_custom_course(course_id: int) -> None:
    with connect_db() as connection:
        connection.execute(
            "DELETE FROM semester_courses WHERE id = ? AND is_custom = 1",
            (course_id,),
        )


def get_course(course_id: int) -> dict[str, Any] | None:
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM semester_courses WHERE id = ?", (course_id,)
        ).fetchone()
    return dict(row) if row else None


def save_course_notes(
    course_id: int, material: str, discussion: str, assignments: str
) -> None:
    with connect_db() as connection:
        connection.execute(
            """
            UPDATE semester_courses
            SET material = ?, discussion = ?, assignments = ?, updated_at = ?
            WHERE id = ?
            """,
            (material, discussion, assignments, utc_now(), course_id),
        )


def save_study_pack(course_id: int, pack: dict[str, Any], provider: str) -> None:
    with connect_db() as connection:
        connection.execute(
            """
            UPDATE semester_courses
            SET study_pack_json = ?, provider = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(pack, ensure_ascii=False), provider, utc_now(), course_id),
        )


def export_semester(semester_id: int) -> str:
    semesters = {item["id"]: item for item in list_semesters()}
    payload = {
        "app": "UT Study Prep",
        "version": 2,
        "exported_at": utc_now(),
        "semester": semesters[semester_id],
        "courses": list_semester_courses(semester_id, active_only=False),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


init_database()


# -----------------------------------------------------------------------------
# Study-pack engines
# -----------------------------------------------------------------------------

STOPWORDS = {
    "about", "after", "again", "akan", "atau", "bagi", "bahwa", "being", "dalam",
    "dapat", "dari", "dengan", "does", "each", "have", "into", "juga", "karena",
    "kepada", "lain", "lebih", "maka", "pada", "para", "sebagai", "sebuah", "serta",
    "sudah", "tersebut", "this", "untuk", "yang", "their", "there", "these", "through",
    "were", "will", "with", "your", "the", "and", "from", "that", "then", "than",
    "when", "where", "which", "while", "what", "over",
}


class ProviderError(RuntimeError):
    pass


def clean_sentences(text: str) -> list[str]:
    compact = re.sub(r"[ \t]+", " ", text.replace("\r", " ")).strip()
    parts = re.split(r"(?<=[.!?])\s+|\n+|(?:^|\s)[•*-]\s+", compact)
    return [part.strip(" -•\t") for part in parts if len(part.strip()) >= 28]


def keywords_for(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}", text.lower())
    counts = Counter(word for word in words if word not in STOPWORDS and not word.isdigit())
    return [word for word, _ in counts.most_common(limit)]


def local_study_pack(
    course: dict[str, Any], material: str, discussion: str, assignments: str
) -> dict[str, Any]:
    combined = "\n".join(part for part in (material, discussion, assignments) if part.strip())
    sentences = clean_sentences(combined) or [combined.strip()]
    keywords = keywords_for(combined, 14)
    fallback = ["concept", "application", "analysis", "process", "evaluation", "design", "system", "quality"]
    for candidate in fallback:
        if len(keywords) >= 8:
            break
        if candidate not in keywords:
            keywords.append(candidate)

    frequency = Counter(re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}", combined.lower()))
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: sum(frequency[word] for word in re.findall(r"\w+", pair[1].lower()))
        / math.sqrt(max(len(pair[1].split()), 1)),
        reverse=True,
    )[: min(5, len(sentences))]
    summary_sentences = [sentences[index] for index, _ in sorted(ranked)]
    summary = " ".join(summary_sentences)

    key_points = [sentence for sentence in summary_sentences[:6]]
    if len(key_points) < 5:
        key_points.extend(
            f"Connect {keyword.title()} to the learning outcomes for {course['name']}."
            for keyword in keywords[: 5 - len(key_points)]
        )

    discussion_topics = keywords_for(discussion + " " + assignments, 5)
    prediction_topics = list(dict.fromkeys(discussion_topics + keywords))[:5]
    exam_predictions = [
        {
            "topic": topic.title(),
            "priority": "High" if index < 2 else "Medium",
            "rationale": (
                "Repeated in discussion or assignment prompts; practice explaining and applying it."
                if topic in discussion_topics
                else "Prominent in the supplied Tuton material and likely to support a concept question."
            ),
        }
        for index, topic in enumerate(prediction_topics)
    ]

    flashcards = []
    for topic in keywords[:6]:
        evidence = next(
            (sentence for sentence in sentences if topic.lower() in sentence.lower()),
            f"Review how {topic} relates to {course['name']} using your Tuton material.",
        )
        flashcards.append(
            {"front": f"What should you remember about {topic.title()}?", "back": evidence}
        )

    quiz = []
    for index, topic in enumerate(keywords[:5]):
        source_sentence = next(
            (sentence for sentence in sentences if topic.lower() in sentence.lower()),
            key_points[index % len(key_points)],
        )
        distractors = [word.title() for word in keywords if word != topic][:3]
        while len(distractors) < 3:
            distractors.append(["Implementation", "Evaluation", "Architecture"][len(distractors)])
        answer_index = index % 4
        options = distractors[:]
        options.insert(answer_index, topic.title())
        quiz.append(
            {
                "question": f"Which concept best matches this note: “{source_sentence[:150]}”?",
                "options": options,
                "answer_index": answer_index,
                "explanation": f"The note most directly describes {topic.title()}.",
            }
        )

    return {
        "summary": summary,
        "key_points": key_points[:6],
        "exam_predictions": exam_predictions,
        "flashcards": flashcards,
        "quiz": quiz,
        "study_plan": [
            "Read the summary once without highlighting.",
            "Recall every key point without looking at the notes.",
            "Practice the predicted UAS topics with your own examples.",
            "Complete the quiz, then revisit every missed concept.",
        ],
    }


def provider_prompt(
    course: dict[str, Any], material: str, discussion: str, assignments: str
) -> str:
    source = f"""
COURSE: {course['code']} — {course['name']} ({course['credits']} SKS)

TUTON MATERIAL:
{material}

DISCUSSION QUESTIONS:
{discussion or '(none supplied)'}

ASSIGNMENTS:
{assignments or '(none supplied)'}
""".strip()[:30000]
    return f"""
You are an exam-preparation assistant for a Universitas Terbuka Information Systems student.
Use only the supplied course material. Write in the main language used by the source. Never claim
that a predicted topic is guaranteed to appear in the UAS. Return only one valid JSON object with:

{{
  "summary": "a concise but complete summary",
  "key_points": ["5 to 7 important points"],
  "exam_predictions": [
    {{"topic": "topic", "priority": "High or Medium", "rationale": "evidence-based reason"}}
  ],
  "flashcards": [{{"front": "question", "back": "answer"}}],
  "quiz": [
    {{"question": "multiple-choice question", "options": ["A", "B", "C", "D"],
      "answer_index": 0, "explanation": "why the answer is correct"}}
  ],
  "study_plan": ["four short actions"]
}}

Create 5 exam predictions, 6 flashcards, and 5 quiz questions. The answer_index is zero-based.

{source}
""".strip()


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            message = detail.get("error", {}).get("message") or str(detail)
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = f"HTTP {exc.code}"
        raise ProviderError(f"Provider request failed: {message}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"Could not reach the AI provider: {exc}") from exc


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise ProviderError("The provider did not return a JSON study pack.")
    try:
        result = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError("The provider returned malformed JSON. Please try again.") from exc
    if not isinstance(result, dict):
        raise ProviderError("The provider response was not a study-pack object.")
    return normalize_study_pack(result)


def normalize_study_pack(pack: dict[str, Any]) -> dict[str, Any]:
    summary = str(pack.get("summary", "")).strip()
    key_points = [str(item).strip() for item in pack.get("key_points", []) if str(item).strip()]
    predictions = []
    for item in pack.get("exam_predictions", []):
        if isinstance(item, dict) and item.get("topic"):
            predictions.append(
                {
                    "topic": str(item["topic"]).strip(),
                    "priority": str(item.get("priority", "Medium")).strip(),
                    "rationale": str(item.get("rationale", "Review this recurring concept.")).strip(),
                }
            )
    flashcards = []
    for item in pack.get("flashcards", []):
        if isinstance(item, dict):
            front = str(item.get("front", "")).strip()
            back = str(item.get("back", "")).strip()
            if front and back:
                flashcards.append({"front": front, "back": back})
    quiz = []
    for item in pack.get("quiz", []):
        if not isinstance(item, dict):
            continue
        options = [str(option).strip() for option in item.get("options", [])]
        try:
            answer_index = int(item.get("answer_index", 0))
        except (TypeError, ValueError):
            answer_index = 0
        if item.get("question") and len(options) == 4 and 0 <= answer_index < 4:
            quiz.append(
                {
                    "question": str(item["question"]).strip(),
                    "options": options,
                    "answer_index": answer_index,
                    "explanation": str(item.get("explanation", "")).strip(),
                }
            )
    study_plan = [str(item).strip() for item in pack.get("study_plan", []) if str(item).strip()]
    if not summary or len(key_points) < 3 or len(predictions) < 2 or len(flashcards) < 3 or len(quiz) < 3:
        raise ProviderError("The provider response was incomplete. Please generate it again.")
    return {
        "summary": summary,
        "key_points": key_points[:8],
        "exam_predictions": predictions[:6],
        "flashcards": flashcards[:8],
        "quiz": quiz[:6],
        "study_plan": study_plan[:6],
    }


def gemini_study_pack(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    safe_model = urllib.parse.quote(model.strip(), safe="-_.")
    data = post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent",
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.25, "responseMimeType": "application/json"},
        },
        {"x-goog-api-key": api_key},
    )
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Gemini returned no usable text.") from exc
    return extract_json(text)


def groq_study_pack(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    data = post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": model.strip(),
            "messages": [
                {"role": "system", "content": "Return only valid JSON for the requested study pack."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        },
        {"Authorization": f"Bearer {api_key}"},
    )
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Groq returned no usable text.") from exc
    return extract_json(text)


def generate_study_pack(
    provider: str,
    course: dict[str, Any],
    material: str,
    discussion: str,
    assignments: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    if provider == "Local (no API)":
        return local_study_pack(course, material, discussion, assignments)
    if not api_key.strip():
        raise ProviderError(f"Enter a {provider} API key in the sidebar first.")
    prompt = provider_prompt(course, material, discussion, assignments)
    if provider == "Google Gemini":
        return gemini_study_pack(prompt, api_key.strip(), model)
    if provider == "Groq":
        return groq_study_pack(prompt, api_key.strip(), model)
    raise ProviderError("Unsupported study engine.")


# -----------------------------------------------------------------------------
# Interface helpers
# -----------------------------------------------------------------------------

APP_CSS = """
<style>
    :root { --ink:#18251f; --pine:#16453e; --mint:#dcece5; --sand:#f7f2e8; --coral:#d46c4e; }
    .stApp { background: linear-gradient(135deg, #fbf9f3 0%, #f2f7f4 52%, #eef3f5 100%); }
    [data-testid="stSidebar"] { background:#163b36; }
    [data-testid="stSidebar"] * { color:#f6fbf8 !important; }
    [data-testid="stSidebar"] input { color:#18251f !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] * { color:#18251f !important; }
    h1, h2, h3 { letter-spacing:-0.025em; color:var(--ink); }
    .hero { padding:1.4rem 1.55rem; border:1px solid #d8e5df; border-radius:22px;
            background:linear-gradient(120deg,#fffdf8,#e5f1eb); margin-bottom:1.2rem; }
    .eyebrow { color:#a54d38; font-size:.76rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
    .hero p { color:#50625a; max-width:780px; margin:.35rem 0 0; }
    .course-chip { display:inline-block; padding:.25rem .6rem; border-radius:999px; background:#dcece5;
                   color:#16453e; font-size:.78rem; font-weight:700; margin-right:.35rem; }
    .prediction { border-left:4px solid #d46c4e; background:#fffaf4; padding:.8rem 1rem;
                  border-radius:0 12px 12px 0; margin:.55rem 0; }
    .flashcard { min-height:145px; padding:1rem; border:1px solid #d7e1dc; border-radius:16px;
                 background:white; box-shadow:0 8px 25px rgba(30,60,50,.06); }
    .muted { color:#65756e; font-size:.9rem; }
    div[data-testid="stMetric"] { background:rgba(255,255,255,.82); border:1px solid #dce6e0;
                                  padding:.8rem; border-radius:16px; }
</style>
"""

DEMO_MATERIAL = """Information systems combine people, processes, data, and technology to support
operations and managerial decisions. A transaction processing system records routine events, while
management information systems transform operational data into scheduled reports. Decision support
systems use models and data analysis for semi-structured decisions. System quality, information
quality, user adoption, security, and business alignment are important measures of success."""


def configured_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, AttributeError):
        value = ""
    return str(value or os.getenv(name, ""))


def parse_pack(course: dict[str, Any]) -> dict[str, Any] | None:
    raw = course.get("study_pack_json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def load_demo_material(course_id: int) -> None:
    st.session_state[f"material_{course_id}"] = DEMO_MATERIAL
    st.session_state[f"discussion_{course_id}"] = (
        "Compare transaction processing systems, management information systems, and decision support systems."
    )
    st.session_state[f"assignments_{course_id}"] = (
        "Explain how information quality and user adoption affect information-system success."
    )


def audio_reader(text: str, course_id: int) -> None:
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
    st.iframe(
        f"""
        <div style="font-family:Arial,sans-serif;background:#eef6f2;border:1px solid #d3e5dc;
                    border-radius:14px;padding:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <strong style="color:#16453e;margin-right:8px">Audio reader</strong>
          <button id="play-{course_id}" style="border:0;border-radius:999px;padding:8px 14px;background:#16453e;color:white;cursor:pointer">▶ Listen</button>
          <button id="pause-{course_id}" style="border:1px solid #16453e;border-radius:999px;padding:8px 14px;background:white;color:#16453e;cursor:pointer">Pause / resume</button>
          <button id="stop-{course_id}" style="border:0;border-radius:999px;padding:8px 14px;background:#d46c4e;color:white;cursor:pointer">Stop</button>
          <select id="lang-{course_id}" style="padding:7px;border-radius:8px;border:1px solid #aac4b8">
            <option value="id-ID">Bahasa Indonesia</option><option value="en-US">English</option>
          </select>
        </div>
        <script>
          const studyBytes = Uint8Array.from(atob('{encoded_text}'), character => character.charCodeAt(0));
          const studyText = new TextDecoder().decode(studyBytes);
          const synth = window.speechSynthesis;
          let utterance = null;
          document.getElementById('play-{course_id}').onclick = () => {{
            synth.cancel(); utterance = new SpeechSynthesisUtterance(studyText);
            utterance.lang = document.getElementById('lang-{course_id}').value;
            utterance.rate = 0.95; synth.speak(utterance);
          }};
          document.getElementById('pause-{course_id}').onclick = () => synth.paused ? synth.resume() : synth.pause();
          document.getElementById('stop-{course_id}').onclick = () => synth.cancel();
        </script>
        """,
        height=88,
    )


def render_pack(pack: dict[str, Any], course: dict[str, Any]) -> None:
    summary_tab, predictor_tab, cards_tab, quiz_tab = st.tabs(
        ["Summary & audio", "UAS predictor", "Flashcards", "Practice quiz"]
    )
    with summary_tab:
        st.markdown(pack["summary"])
        audio_reader(pack["summary"], int(course["id"]))
        st.markdown("#### Key points")
        for point in pack.get("key_points", []):
            st.markdown(f"- {point}")
        if pack.get("study_plan"):
            st.markdown("#### Suggested review loop")
            for index, action in enumerate(pack["study_plan"], start=1):
                st.markdown(f"{index}. {action}")

    with predictor_tab:
        st.caption("Predictions are study priorities inferred from your material, not guaranteed UAS questions.")
        for prediction in pack.get("exam_predictions", []):
            st.markdown(
                "<div class='prediction'>"
                f"<strong>{html.escape(prediction['topic'])}</strong> "
                f"<span class='course-chip'>{html.escape(prediction['priority'])}</span><br>"
                f"<span class='muted'>{html.escape(prediction['rationale'])}</span></div>",
                unsafe_allow_html=True,
            )

    with cards_tab:
        cards = pack.get("flashcards", [])
        columns = st.columns(2)
        for index, card in enumerate(cards):
            with columns[index % 2]:
                st.markdown(
                    "<div class='flashcard'>"
                    f"<strong>{html.escape(card['front'])}</strong><hr>"
                    f"<span class='muted'>{html.escape(card['back'])}</span></div>",
                    unsafe_allow_html=True,
                )

    with quiz_tab:
        quiz = pack.get("quiz", [])
        with st.form(f"quiz_form_{course['id']}_{course.get('updated_at', '')}"):
            answers: list[str | None] = []
            for index, question in enumerate(quiz):
                answers.append(
                    st.radio(
                        f"{index + 1}. {question['question']}",
                        question["options"],
                        index=None,
                        key=f"quiz_{course['id']}_{index}_{course.get('updated_at', '')}",
                    )
                )
            submitted = st.form_submit_button("Check my answers", type="primary")
        if submitted:
            score = 0
            for index, (question, answer) in enumerate(zip(quiz, answers), start=1):
                correct = question["options"][question["answer_index"]]
                if answer == correct:
                    score += 1
                    st.success(f"Question {index}: correct")
                else:
                    st.error(f"Question {index}: the correct answer is {correct}")
                if question.get("explanation"):
                    st.caption(question["explanation"])
            st.metric("Quiz score", f"{score}/{len(quiz)}")


def hero(title: str, copy: str, eyebrow: str = "NON-SIPAS STUDY SYSTEM") -> None:
    st.markdown(
        "<div class='hero'>"
        f"<div class='eyebrow'>{html.escape(eyebrow)}</div>"
        f"<h1>{html.escape(title)}</h1><p>{html.escape(copy)}</p></div>",
        unsafe_allow_html=True,
    )


st.markdown(APP_CSS, unsafe_allow_html=True)
semesters = list_semesters()
semester_lookup = {item["id"]: item for item in semesters}
pending_semester_id = st.session_state.pop("_pending_semester_id", None)
if pending_semester_id in semester_lookup:
    st.session_state["semester_selector"] = pending_semester_id

with st.sidebar:
    st.markdown("# UT Study Prep")
    st.caption("Flexible Non-SIPAS semester planning")
    page = st.radio("Navigate", ["Semester setup", "Course workspace", "Master catalog"])
    semester_id = st.selectbox(
        "Active semester",
        options=list(semester_lookup),
        format_func=lambda item_id: semester_lookup[item_id]["name"],
        key="semester_selector",
    )
    with st.expander("Create another semester"):
        with st.form("new_semester_form"):
            new_semester_name = st.text_input("Semester name", placeholder="Semester 6")
            create_clicked = st.form_submit_button("Create semester")
        if create_clicked:
            try:
                new_id = create_semester(new_semester_name)
                st.session_state["_pending_semester_id"] = new_id
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    st.markdown("#### Study engine")
    provider = st.selectbox(
        "Provider",
        ["Local (no API)", "Google Gemini", "Groq"],
        help="Local mode is always free. Gemini and Groq can use their provider free tiers, subject to current quotas.",
    )
    if provider == "Google Gemini":
        api_key = st.text_input(
            "Gemini API key",
            value=configured_secret("GEMINI_API_KEY"),
            type="password",
            help="Kept only in this browser session unless configured as an environment variable or Streamlit secret.",
        )
        model = st.text_input("Gemini model", value="gemini-2.5-flash", key="gemini_model")
        st.link_button("Get a Gemini API key", "https://aistudio.google.com/app/apikey")
    elif provider == "Groq":
        api_key = st.text_input(
            "Groq API key",
            value=configured_secret("GROQ_API_KEY"),
            type="password",
            help="Kept only in this browser session unless configured as an environment variable or Streamlit secret.",
        )
        model = st.text_input("Groq model", value="llama-3.3-70b-versatile", key="groq_model")
        st.link_button("Get a Groq API key", "https://console.groq.com/keys")
    else:
        api_key, model = "", "local-keyword-engine"
    st.caption(f"Study data: `{DB_PATH.name}`")


if page == "Semester setup":
    hero(
        "Build your semester, your way.",
        "Non-SIPAS mode lets you choose any active courses from the UT Information Systems catalog and add a custom course when needed.",
    )
    existing = list_semester_courses(semester_id, active_only=False)
    selected_catalog = [
        course["code"] for course in existing if not course["is_custom"] and course["active"]
    ]
    active = [course for course in existing if course["active"]]
    active_credits = sum(int(course["credits"]) for course in active)
    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Active courses", len(active))
    metric_two.metric("Selected load", f"{active_credits} SKS")
    metric_three.metric("Master catalog", "60 offerings")

    st.subheader("Select active catalog courses")
    with st.form(f"catalog_form_{semester_id}"):
        choices = st.multiselect(
            "Courses for this semester",
            options=[course["code"] for course in CATALOG_MK_UT],
            default=selected_catalog,
            format_func=lambda code: (
                f"{code} — {CATALOG_BY_CODE[code]['name']} · {CATALOG_BY_CODE[code]['credits']} SKS"
            ),
            key=f"catalog_selection_{semester_id}",
        )
        save_selection = st.form_submit_button("Save active courses", type="primary")
    if save_selection:
        sync_catalog_selection(semester_id, choices)
        st.success("Active catalog courses saved to SQLite.")

    with st.expander("Add custom course"):
        with st.form(f"custom_course_{semester_id}", clear_on_submit=True):
            custom_left, custom_mid, custom_right = st.columns([1, 2, 1])
            custom_code = custom_left.text_input("Code", placeholder="CUSTOM01")
            custom_name = custom_mid.text_input("Course name")
            custom_credits = custom_right.number_input("SKS", min_value=1, max_value=24, value=3)
            add_custom = st.form_submit_button("Add custom course")
        if add_custom:
            try:
                add_custom_course(semester_id, custom_code, custom_name, int(custom_credits))
                st.success("Custom course added.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Current active courses")
    active = list_semester_courses(semester_id)
    if not active:
        st.info("No active courses yet. Select catalog courses above or add a custom course.")
    else:
        st.dataframe(
            [
                {
                    "Code": course["code"], "Course": course["name"], "SKS": course["credits"],
                    "Source": "Custom" if course["is_custom"] else "UT catalog",
                    "Study pack": "Ready" if course["study_pack_json"] else "Not generated",
                }
                for course in active
            ],
            width="stretch",
            hide_index=True,
        )
        custom_courses = [course for course in active if course["is_custom"]]
        if custom_courses:
            with st.expander("Manage custom courses"):
                for course in custom_courses:
                    left, right = st.columns([5, 1])
                    left.write(f"**{course['code']}** — {course['name']} ({course['credits']} SKS)")
                    if right.button("Remove", key=f"remove_custom_{course['id']}"):
                        remove_custom_course(int(course["id"]))
                        st.rerun()

    st.download_button(
        "Download semester backup (JSON)",
        data=export_semester(semester_id),
        file_name=f"{semester_lookup[semester_id]['name'].lower().replace(' ', '-')}-backup.json",
        mime="application/json",
    )

elif page == "Course workspace":
    hero(
        "Turn each Tuton course into an exam plan.",
        "Save materials by active course, generate a focused summary, listen to it, and practice the UAS priorities.",
    )
    active_courses = list_semester_courses(semester_id)
    if not active_courses:
        st.info("Choose active courses in Semester setup before opening the study workspace.")
        st.stop()

    course_map = {int(course["id"]): course for course in active_courses}
    course_id = st.selectbox(
        "Active course",
        options=list(course_map),
        format_func=lambda item_id: f"{course_map[item_id]['code']} — {course_map[item_id]['name']}",
        key=f"workspace_course_{semester_id}",
    )
    course = get_course(course_id)
    if course is None:
        st.error("This course could not be loaded.")
        st.stop()

    st.markdown(
        f"<span class='course-chip'>{html.escape(course['code'])}</span>"
        f"<span class='course-chip'>{course['credits']} SKS</span>",
        unsafe_allow_html=True,
    )
    st.subheader(course["name"])
    material = st.text_area(
        "Tuton material", value=course["material"], height=260,
        placeholder="Paste module notes, Tuton explanations, or learning outcomes…",
        key=f"material_{course_id}",
    )
    notes_left, notes_right = st.columns(2)
    with notes_left:
        discussion = st.text_area(
            "Discussion questions", value=course["discussion"], height=145,
            key=f"discussion_{course_id}",
        )
    with notes_right:
        assignments = st.text_area(
            "Assignments", value=course["assignments"], height=145,
            key=f"assignments_{course_id}",
        )

    action_one, action_two, action_three, action_space = st.columns([1, 1.4, 1, 2])
    save_clicked = action_one.button("Save notes", width="stretch")
    generate_clicked = action_two.button("Generate study pack", type="primary", width="stretch")
    action_three.button(
        "Load demo", width="stretch", on_click=load_demo_material, args=(course_id,)
    )

    if save_clicked:
        save_course_notes(course_id, material, discussion, assignments)
        st.success("Course notes saved locally.")

    pack = parse_pack(course)
    if generate_clicked:
        if len(material.strip()) + len(discussion.strip()) + len(assignments.strip()) < 80:
            st.error("Add at least 80 characters of Tuton material before generating a study pack.")
        else:
            save_course_notes(course_id, material, discussion, assignments)
            try:
                with st.spinner(f"Building the study pack with {provider}…"):
                    pack = generate_study_pack(
                        provider, course, material, discussion, assignments, api_key, model
                    )
                save_study_pack(course_id, pack, provider)
                course = get_course(course_id) or course
                st.success(f"Study pack generated with {provider} and saved locally.")
            except ProviderError as exc:
                st.error(str(exc))

    if pack:
        st.divider()
        st.caption(f"Saved study pack · {course.get('provider') or provider}")
        render_pack(pack, course)
    else:
        st.info("Save your Tuton material, then generate the first study pack for this course.")

else:
    hero(
        "UT Information Systems master catalog.",
        "All 60 course offerings are listed individually so Non-SIPAS students can freely build an active semester.",
        eyebrow="MASTER CATALOG",
    )
    search = st.text_input("Search by code or course name", placeholder="Try STSI44 or security")
    query = search.strip().lower()
    filtered = [
        course for course in CATALOG_MK_UT
        if not query or query in course["code"].lower() or query in course["name"].lower()
    ]
    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Course offerings", len(CATALOG_MK_UT))
    metric_two.metric("Showing", len(filtered))
    metric_three.metric("Study system", "Non-SIPAS")
    st.dataframe(
        [{"Code": course["code"], "Course": course["name"], "SKS": course["credits"]} for course in filtered],
        width="stretch",
        hide_index=True,
    )
    st.info(
        "Religious-education and elective alternatives appear as separate offerings. "
        "Their SKS values should not be summed as one required study plan."
    )
