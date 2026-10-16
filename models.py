"""Typed data contracts shared by the local and AI study engines."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


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

