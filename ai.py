"""Optional OpenAI-backed study-pack generation."""

from __future__ import annotations

from openai import OpenAI

from .models import StudyPack


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

