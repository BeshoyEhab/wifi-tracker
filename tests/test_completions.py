import contextlib
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.cli import _handle_completion


def run_completion(shell, comp_word, comp_words):
    old = os.environ.get("COMP_WORDS")
    os.environ["COMP_WORDS"] = comp_words
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            _handle_completion(shell, comp_word)
    finally:
        if old is None:
            os.environ.pop("COMP_WORDS", None)
        else:
            os.environ["COMP_WORDS"] = old
    return buf.getvalue().splitlines()


class TestCompletionOutput(unittest.TestCase):
    def test_fish_returns_one_suggestion_per_line(self):
        out = run_completion("fish", "", "wifi-tracker perapp")
        self.assertEqual(out, ["install", "remove", "status"])

    def test_zsh_returns_one_suggestion_per_line(self):
        out = run_completion("zsh", "", "wifi-tracker perapp")
        self.assertEqual(out, ["install", "remove", "status"])

    def test_bash_returns_columnar_output(self):
        out = run_completion("bash", "", "wifi-tracker perapp")
        self.assertEqual(len(out), 1)
        self.assertEqual("".join(out).split(), ["install", "remove", "status"])

    def test_zsh_has_no_padded_whitespace_in_entries(self):
        out = run_completion("zsh", "", "wifi-tracker")
        for line in out:
            self.assertFalse("  " in line, f"zsh entry has padding: {line!r}")


if __name__ == "__main__":
    unittest.main()
