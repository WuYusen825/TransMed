from __future__ import annotations

import json
import unittest
from pathlib import Path

from transmed_app.recommendation_engine import analyze_symptoms


CASES = json.loads((Path(__file__).with_name("recommendation_cases.json")).read_text(encoding="utf-8"))


class TriageBenchmarkTests(unittest.TestCase):
    def test_bilingual_benchmark(self) -> None:
        for case in CASES:
            with self.subTest(case=case["input"]):
                result = analyze_symptoms(case["input"])
                self.assertEqual(result["department_en"], case["department"])
                self.assertEqual(result["urgent"], case["urgent"])
                if "min_confidence" in case:
                    self.assertGreaterEqual(result["confidence"], case["min_confidence"])
                if "max_confidence" in case:
                    self.assertLessEqual(result["confidence"], case["max_confidence"])

    def test_low_information_requests_clarification(self) -> None:
        result = analyze_symptoms("不舒服")
        self.assertTrue(result["needs_clarification"])
        self.assertGreaterEqual(len(result["follow_up_questions"]), 2)

    def test_low_mood_routes_to_mental_health_with_safety_question(self) -> None:
        result = analyze_symptoms("心情不好")
        self.assertEqual(result["department_en"], "Mental Health / Psychiatry")
        self.assertFalse(result["urgent"])
        self.assertTrue(any("伤害自己" in item or "不想活" in item for item in result["follow_up_questions"]))

    def test_negated_red_flag_does_not_make_case_urgent(self) -> None:
        result = analyze_symptoms("没有胸痛，也没有呼吸困难，只有咳嗽")
        self.assertEqual(result["department_en"], "Pulmonary / Respiratory")
        self.assertFalse(result["urgent"])
        self.assertNotIn("胸痛", result["matched_symptoms"])


class HospitalRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Importing backend initializes the lightweight local DB, so keep it out
        # of module collection and do it once for this test class.
        from transmed_app.backend import _recommendation_score
        from transmed_app.hospital_dataset import HOSPITALS_EXT

        cls.score = staticmethod(_recommendation_score)
        cls.beijing = [dict(item, capability_source="curated_profile") for item in HOSPITALS_EXT if item.get("city") == "北京"]

    def _rank(self, specialty: str, confidence: float = 0.9) -> list[tuple[float, dict, dict]]:
        rows = []
        for hospital in self.beijing:
            rec = self.score(hospital, {specialty: 100.0}, language="zh", triage_confidence=confidence)
            if rec["eligible"]:
                rows.append((rec["score"], hospital, rec))
        return sorted(rows, key=lambda row: (-row[0], row[1]["name_zh"]))

    def test_psychiatry_leaders_outrank_unrelated_hospitals(self) -> None:
        rows = self._rank("Mental Health / Psychiatry", confidence=0.76)
        self.assertEqual({row[1]["id"] for row in rows[:2]}, {"bj-anding", "bj-pku6"})
        self.assertTrue(all(row[0] < 100 for row in rows))

    def test_cardiology_leaders_are_first(self) -> None:
        rows = self._rank("Cardiology")
        self.assertEqual({row[1]["id"] for row in rows[:2]}, {"bj-fuwai", "bj-anzhen"})

    def test_dental_leader_is_first(self) -> None:
        rows = self._rank("Dental")
        self.assertEqual(rows[0][1]["id"], "bj-stomatology")

    def test_unknown_wait_and_distance_earn_no_points(self) -> None:
        generic = {
            "id": "generic",
            "name": "Nearby Generic Hospital",
            "name_zh": "附近综合医院",
            "specialties": ["医疗保健服务", "综合医院"],
            "languages": ["Chinese"],
            "rating": 5.0,
            "wait_minutes": 0,
            "distance_km": None,
            "capability_source": "amap_poi",
        }
        rec = self.score(generic, {"Mental Health / Psychiatry": 100.0}, language="zh", triage_confidence=0.76)
        self.assertFalse(rec["eligible"])
        self.assertEqual(rec["wait_score"], 0)
        self.assertEqual(rec["distance_score"], 0)
        self.assertLess(rec["score"], 15)

    def test_short_ent_name_does_not_match_mental(self) -> None:
        hospital = {
            "id": "ent-only",
            "name": "ENT Hospital",
            "name_zh": "耳鼻喉医院",
            "specialties": ["ENT"],
            "languages": ["Chinese"],
            "capability_source": "curated_profile",
        }
        rec = self.score(hospital, {"Mental Health / Psychiatry": 100.0}, triage_confidence=0.8)
        self.assertFalse(rec["eligible"])
        self.assertEqual(rec["specialty_evidence"]["Mental Health / Psychiatry"], 0)


class RecommendationEndpointTests(unittest.TestCase):
    def test_screenshot_case_returns_only_verified_psychiatry_hospitals(self) -> None:
        from transmed_app.backend import RecommendationIn, recommendations_api

        result = recommendations_api(RecommendationIn(symptoms="心情不好", city="北京", language="zh", limit=10))
        self.assertEqual(result["triage"]["department_en"], "Mental Health / Psychiatry")
        self.assertTrue(result["triage"]["needs_clarification"])
        self.assertEqual({item["id"] for item in result["hospitals"]}, {"bj-anding", "bj-pku6"})
        self.assertTrue(all(item["recommendation"]["score"] < 100 for item in result["hospitals"]))
        self.assertEqual(result["recommendation_meta"]["ranking_engine"], "hospital-fit-v2.0")

    def test_beijing_candidates_do_not_include_other_explicit_cities(self) -> None:
        from transmed_app.backend import _fetch_candidate_hospitals

        result = _fetch_candidate_hospitals({"Mental Health / Psychiatry": 100.0}, "北京", 10)
        wrong_city = [item for item in result["hospitals"] if item.get("city") not in (None, "", "北京")]
        self.assertEqual(wrong_city, [])

    def test_get_hospitals_uses_the_same_verified_ranking_path(self) -> None:
        from transmed_app.backend import hospitals_list

        result = hospitals_list(city="北京", symptom="心情不好", language="zh", limit=10)
        self.assertEqual({item["id"] for item in result["hospitals"]}, {"bj-anding", "bj-pku6"})


if __name__ == "__main__":
    unittest.main()
