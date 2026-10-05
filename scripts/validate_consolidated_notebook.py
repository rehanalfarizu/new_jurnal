"""Validate a clean publication artifact, then execute it in reviewer mode.

This validation intentionally supplies a nonexistent raw-dataset path. Scientific
source, configs, frozen notebooks, and results are hashed before and after the
execution so that notebook validation cannot silently alter frozen artifacts.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import nbformat
from nbclient import NotebookClient

from notebook_quality import publication_hygiene_checks


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/00_complete_research_workflow.ipynb"
PROTECTED_PATHS = (
    "configs",
    "results",
    "src",
    "scripts/notebook_quality.py",
    "notebooks/01_dataset_exploration.ipynb",
    "notebooks/02_canonical_twin_state.ipynb",
    "notebooks/03_baseline_forecasting.ipynb",
    "notebooks/04_occupancy_ablation.ipynb",
    "notebooks/05_digital_twin_evaluation.ipynb",
    "notebooks/06_decision_support_analysis.ipynb",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def protected_checksums() -> dict[str, str]:
    command = ["git", "ls-files", "-z", "--", *PROTECTED_PATHS]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    relative_paths = [
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    return {relative: sha256(ROOT / relative) for relative in relative_paths}


def main() -> None:
    source_checksum_before = sha256(NOTEBOOK)
    protected_before = protected_checksums()

    with tempfile.TemporaryDirectory(prefix="new_jurnal_notebook_") as temp_dir:
        temp_path = Path(temp_dir)
        missing_dataset = temp_path / "sensor_data.csv"
        if missing_dataset.exists():
            raise AssertionError("The clean-execution dataset path must not exist.")

        previous_dataset_path = os.environ.get("SENSOR_DATA_PATH")
        os.environ["SENSOR_DATA_PATH"] = str(missing_dataset)
        try:
            notebook = nbformat.read(NOTEBOOK, as_version=4)
            nbformat.validate(notebook)
            hygiene = publication_hygiene_checks(notebook)
            failures = [label for label, passed in hygiene.items() if not passed]
            if failures:
                raise AssertionError(
                    "Publication copy must be clean before validation: "
                    + "; ".join(failures)
                    + ". Saved outputs are allowed in a local working notebook, "
                    "but clear them in the copy prepared for Git."
                )
            kernel_name = os.environ.get("NOTEBOOK_KERNEL_NAME", "python3")
            client = NotebookClient(
                notebook,
                timeout=600,
                kernel_name=kernel_name,
                resources={"metadata": {"path": str(ROOT)}},
            )
            executed = client.execute()
            nbformat.write(executed, temp_path / "00_complete_research_workflow.executed.ipynb")
        finally:
            if previous_dataset_path is None:
                os.environ.pop("SENSOR_DATA_PATH", None)
            else:
                os.environ["SENSOR_DATA_PATH"] = previous_dataset_path

    if sha256(NOTEBOOK) != source_checksum_before:
        raise AssertionError("Notebook source changed during temporary execution.")
    if protected_checksums() != protected_before:
        raise AssertionError("A protected scientific file changed during notebook execution.")

    print("Consolidated notebook clean execution: PASS")
    print("Raw dataset supplied: No")
    print("Protected scientific files unchanged: PASS")


if __name__ == "__main__":
    main()
