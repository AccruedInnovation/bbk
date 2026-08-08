from pathlib import Path
path = Path("delivered/frontier.txt")
if path.read_text(encoding="utf-8") != "frontier-executed\n":
    raise SystemExit("frontier output mismatch")
print("PASS")
