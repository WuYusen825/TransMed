from __future__ import annotations

import unittest

from transmed_app.data import SPECIALTY_ALIASES
from transmed_app.hospital_dataset import HOSPITALS_EXT
from transmed_app.recommendation_engine import DEPARTMENT_ZH
from transmed_app.semantic_triage import _literal_evidence


class SemanticTriageContractTests(unittest.TestCase):
    def test_semantic_ontology_covers_all_canonical_specialties(self) -> None:
        self.assertEqual(set(SPECIALTY_ALIASES) - set(DEPARTMENT_ZH), set())

    def test_model_evidence_must_be_a_literal_source_span(self) -> None:
        source = "source-token"
        self.assertEqual(_literal_evidence(source, ["normalized concept"]), [])
        self.assertEqual(_literal_evidence(source, ["source-token"]), ["source-token"])

    def test_burn_service_has_a_verified_beijing_capability_profile(self) -> None:
        profiles = [item for item in HOSPITALS_EXT if item.get("city") == "北京"]
        self.assertTrue(any("Plastic Surgery" in item.get("specialties", []) for item in profiles))


if __name__ == "__main__":
    unittest.main()
