import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EntrypointImportTests(unittest.TestCase):
    def test_entrypoint_modules_import_in_fresh_process(self) -> None:
        command = [
            sys.executable,
            "-c",
            "import apps.api.main; import apps.web.main; import apps.worker.main",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            0,
            completed.returncode,
            completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
