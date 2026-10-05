"""Regression checks for post-freeze reviewer evidence, not new experiments."""

import csv
import hashlib
import json
from pathlib import Path
import unittest

import pandas as pd
import yaml

from src.features.time_series import FEATURE_DEFINITIONS, OCCUPANCY_FEATURES
from src.twin_state.canonical import RAW_COLUMNS


ROOT = Path(__file__).resolve().parents[1]


class ReviewerEvidenceTest(unittest.TestCase):
    def test_raw_excerpt_integrity_schema_and_frozen_source_link(self):
        manifest = json.loads(
            (ROOT / "docs/evidence/raw_dataset_sample_manifest.json").read_text()
        )
        freeze = json.loads(
            (ROOT / "results/metrics/reproducibility_freeze_manifest.json").read_text()
        )
        sample = ROOT / manifest["sample_file"]
        self.assertEqual(
            hashlib.sha256(sample.read_bytes()).hexdigest(), manifest["sample_sha256"]
        )
        self.assertEqual(manifest["source_sha256"], freeze["dataset"]["sha256"])
        with sample.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, list(RAW_COLUMNS.values()))
            self.assertEqual(reader.fieldnames, manifest["source_columns"])
        self.assertEqual(len(rows), manifest["sample_record_count"])
        self.assertEqual(len(rows), 8)
        self.assertEqual(manifest["source_data_row_numbers"], list(range(1, 9)))
        self.assertEqual(rows[0]["Timestamp"], "2026-02-23 23:14:43.896301")
        self.assertEqual(rows[0]["Daya (W)"], "484.0")

    def test_eleven_occupancy_definitions_match_source_and_config(self):
        table = pd.read_csv(
            ROOT / "results/tables/occupancy_ablation_feature_definition.csv"
        )
        occupancy = table.loc[
            table["occupancy_feature"].astype(str).str.lower().eq("true")
        ]
        config = yaml.safe_load((ROOT / "configs/features.yaml").read_text())
        feature_sets = config["model_feature_sets"]
        control = feature_sets["non_occupancy_multivariate_ridge"]
        treatment = feature_sets["occupancy_multivariate_ridge"]
        self.assertEqual(len(control), 20)
        self.assertEqual(len(treatment), 31)
        self.assertEqual(occupancy["feature"].tolist(), OCCUPANCY_FEATURES)
        self.assertEqual(
            [name for name in treatment if name not in control], OCCUPANCY_FEATURES
        )
        self.assertEqual(len(occupancy), 11)
        for _, row in occupancy.iterrows():
            for field in ("description", "source_offset_min", "source_offset_max", "unit"):
                self.assertEqual(row[field], FEATURE_DEFINITIONS[row["feature"]][field])
            self.assertLessEqual(row["source_offset_max"], 0)
            self.assertFalse(row["used_by_control"])
            self.assertTrue(row["used_by_treatment"])

    def test_acquisition_evidence_does_not_assert_verified_deployment(self):
        evidence = json.loads(
            (ROOT / "docs/evidence/occupancy_acquisition_evidence.json").read_text()
        )
        self.assertFalse(evidence["dataset_deployment_link_verified"])
        self.assertFalse(
            evidence["inspected_implementation"]["deployment_at_dataset_collection_verified"]
        )
        self.assertEqual(len(evidence["items"]), 6)
        counting = next(
            item for item in evidence["items"]
            if item["item"] == "Counting uncertainty and accuracy"
        )
        self.assertEqual(counting["evidence_status"], "Unavailable / not evaluated")
        self.assertEqual(len(evidence["additional_evidence_needed"]), 3)


if __name__ == "__main__":
    unittest.main()
