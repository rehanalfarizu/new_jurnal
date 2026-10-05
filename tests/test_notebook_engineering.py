"""Live execution may save outputs; the publication artifact must stay clean."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from IPython.display import Markdown
import pandas as pd

from scripts.notebook_quality import publication_hygiene_checks, source_engineering_checks


ROOT = Path(__file__).resolve().parents[1]


def example_document():
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [{
            "cell_type": "code", "id": "example-code", "metadata": {},
            "source": ["print('example')\n"], "execution_count": None, "outputs": [],
        }],
    }


def executed_document():
    document = example_document()
    document["cells"][0]["execution_count"] = 31
    document["cells"][0]["outputs"] = [{
        "output_type": "stream", "name": "stdout",
        "text": ["Repository root: /Users/example/project\n"],
    }]
    return document


class NotebookEngineeringTest(unittest.TestCase):
    def test_clean_artifact_passes_both_scopes(self):
        document = example_document()
        self.assertTrue(all(source_engineering_checks(document).values()))
        self.assertTrue(all(publication_hygiene_checks(document).values()))

    def test_saved_outputs_and_local_output_paths_do_not_fail_source_checks(self):
        document = executed_document()
        self.assertTrue(all(source_engineering_checks(document).values()))
        publication = publication_hygiene_checks(document)
        self.assertFalse(publication["Stored outputs equal zero"])
        self.assertFalse(publication["Non-null execution counts equal zero"])
        self.assertFalse(publication["No absolute local home path in published file"])

    def test_hardcoded_local_source_path_still_fails(self):
        document = example_document()
        document["cells"][0]["source"] = ["root = '/Users/example/project'\n"]
        self.assertFalse(
            source_engineering_checks(document)["No absolute local home path in source"]
        )

    def test_credential_assignment_in_source_still_fails(self):
        document = example_document()
        document["cells"][0]["source"] = ["password = 'synthetic-test-value'\n"]
        self.assertFalse(
            source_engineering_checks(document)["No credential assignments in source"]
        )

    def test_duplicate_or_missing_cell_ids_still_fail(self):
        for cell_id in ("example-code", "", None):
            with self.subTest(cell_id=cell_id):
                document = example_document()
                extra = deepcopy(document["cells"][0])
                extra["id"] = cell_id
                document["cells"].append(extra)
                self.assertFalse(
                    source_engineering_checks(document)["Unique non-empty cell IDs"]
                )

    def test_publication_checker_rejects_sensitive_metadata(self):
        document = example_document()
        document["metadata"]["note"] = "password = synthetic-test-value"
        self.assertTrue(all(source_engineering_checks(document).values()))
        self.assertFalse(
            publication_hygiene_checks(document)["No credential assignments in published file"]
        )

    def engineering_namespace(self, document, recompute=False):
        notebook = json.loads(
            (ROOT / "notebooks/00_complete_research_workflow.ipynb").read_text()
        )
        source = next(
            "".join(cell["source"]) for cell in notebook["cells"]
            if cell["id"] == "validate-notebook-engineering"
        )
        namespace = {
            "notebook_document": document, "RECOMPUTE_EXPERIMENTS": recompute,
            "SENSOR_DATA_PATH": Path("data/raw/sensor_data.csv"),
            "os": SimpleNamespace(environ={}), "pd": pd, "Markdown": Markdown,
            "display": lambda *objects: None,
        }
        exec(compile(source, "validate-notebook-engineering", "exec"), namespace)
        return namespace

    def test_actual_engineering_cell_passes_with_saved_execution_output(self):
        namespace = self.engineering_namespace(executed_document())
        self.assertTrue(namespace["engineering_checks"]["Pass"].all())
        self.assertFalse(namespace["publication_checks"]["Pass"].all())

    def test_actual_engineering_cell_retains_actionable_runtime_failures(self):
        with self.assertRaisesRegex(AssertionError, "Read-only experiment mode"):
            self.engineering_namespace(example_document(), recompute=True)
        document = example_document()
        document["cells"][0]["source"] = ["root = '/Users/example/project'\n"]
        with self.assertRaisesRegex(AssertionError, "No absolute local home path in source"):
            self.engineering_namespace(document)


if __name__ == "__main__":
    unittest.main()
