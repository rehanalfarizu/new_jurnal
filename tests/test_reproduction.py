"""Test that metrics reproduce from frozen predictions."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class TestReproduction(unittest.TestCase):
    """Verify metrics reproduce within tolerance without retraining."""

    @classmethod
    def setUpClass(cls) -> None:
        """Run the reproduction check script once."""
        root = Path(__file__).resolve().parent.parent
        script = root / "scripts" / "verify_reproduction.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=root,
        )
        cls.returncode = result.returncode
        cls.stdout = result.stdout
        cls.stderr = result.stderr

        # Load the generated manifest
        manifest_path = root / "results" / "metrics" / "reproduction_check.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                cls.manifest = json.load(f)
        else:
            cls.manifest = None

    def test_reproduction_check_ran_successfully(self) -> None:
        """The reproduction script should complete without error."""
        self.assertEqual(
            self.returncode, 0,
            f"Script failed with stderr:\n{self.stderr}\nstdout:\n{self.stdout}",
        )

    def test_manifest_generated(self) -> None:
        """The reproduction manifest should exist."""
        self.assertIsNotNone(self.manifest, "reproduction_check.json not generated")

    def test_max_abs_diff_within_tolerance(self) -> None:
        """Max absolute difference should be <= 1e-9."""
        if self.manifest is None:
            self.skipTest("Manifest not available")

        max_diff = self.manifest.get("max_abs_diff", float("inf"))
        tolerance = 1e-9
        self.assertLessEqual(
            max_diff,
            tolerance,
            f"Max absolute difference {max_diff:.2e} exceeds tolerance {tolerance:.2e}",
        )


if __name__ == "__main__":
    unittest.main()
