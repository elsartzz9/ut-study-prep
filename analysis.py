"""Small, dependency-light extractive study engine.

The local engine intentionally avoids pretending to be generative AI. It ranks
sentences and concepts from the learner's own notes, then turns the strongest
signals into a useful first-pass study pack.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import random
import re

from .models import Flashcard, Prediction, QuizQuestion, StudyPack


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
    value = re.sub(r"\s+", " ", value).strip()
    return value


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

    prediction_items = _prediction_terms(keywords, discussion, assignments)
    predictions = [
        Prediction(topic=topic, rationale=rationale, confidence=confidence)
        for topic, rationale, confidence in prediction_items
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

