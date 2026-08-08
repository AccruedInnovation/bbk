from pathlib import Path
import sys
expected = "alpha17-compiled-procedure-pass\n"
if "--followup" in sys.argv:
    expected += "followup-reused\n"
actual = Path("input.txt").read_text(encoding="utf-8")
if actual != expected:
    raise SystemExit(f"unexpected input.txt: {actual!r}")
print("PASS")
