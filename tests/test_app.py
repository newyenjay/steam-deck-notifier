import tempfile
import unittest
from pathlib import Path

from app import append_history_record, read_history_rows


class HistoryTests(unittest.TestCase):
    def test_append_and_read_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.csv"
            append_history_record(
                {
                    "timestamp": "2026-01-01 00:00:00 UTC",
                    "package_id": "123",
                    "version": "512",
                    "display_type": "OLED",
                    "available": "True",
                },
                history_file=history_file,
            )
            rows = read_history_rows(history_file=history_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["package_id"], "123")


if __name__ == "__main__":
    unittest.main()
