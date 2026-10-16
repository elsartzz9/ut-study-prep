"""Unit tests for the no-key study engine."""

import unittest

from ut_study_prep.analysis import build_local_study_pack, extract_keywords, split_sentences
from ut_study_prep.models import StudyPack


MATERIAL = """
Constructive alignment connects learning outcomes, learning activities, and assessment.
Learning outcomes should use observable verbs so that achievement can be assessed.
Formative assessment gives feedback during learning and helps a student improve.
Summative assessment evaluates achievement after a unit or course is complete.
Clear rubrics describe performance criteria and support consistent self-assessment.
Timely, specific feedback should identify a practical next step for the learner.
"""


class LocalAnalysisTests(unittest.TestCase):
    def test_sentence_splitter_removes_bullets(self) -> None:
        sentences = split_sentences("- One complete sentence about learning outcomes.\n• Another complete sentence about assessment.")
        self.assertEqual(len(sentences), 2)
        self.assertFalse(sentences[0].startswith("-"))

    def test_keywords_favor_repeated_concepts(self) -> None:
        keywords = extract_keywords(MATERIAL, limit=6)
        lowered = {item.casefold() for item in keywords}
        self.assertTrue({"assessment", "learning"} & lowered)

    def test_builds_complete_study_pack(self) -> None:
        pack = build_local_study_pack(
            MATERIAL,
            "Compare formative and summative assessment. Explain constructive alignment.",
            "Write one observable learning outcome and design a rubric.",
        )
        self.assertIsInstance(pack, StudyPack)
        self.assertGreaterEqual(len(pack.summary), 3)
        self.assertGreaterEqual(len(pack.predictions), 3)
        self.assertGreaterEqual(len(pack.flashcards), 4)
        self.assertGreaterEqual(len(pack.quiz), 4)
        self.assertTrue(all(len(question.options) == 4 for question in pack.quiz))

    def test_short_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_local_study_pack("Too short.")

    def test_pack_round_trip(self) -> None:
        pack = build_local_study_pack(MATERIAL)
        restored = StudyPack.model_validate_json(pack.model_dump_json())
        self.assertEqual(restored.summary, pack.summary)


if __name__ == "__main__":
    unittest.main()
