"""One-shot migration from okf-parser 0.42.8 to the released GraphQL extra."""

from pathlib import Path

path = Path("pyproject.toml")
text = path.read_text(encoding="utf-8")
old = '    "okf-parser==0.42.8",\n'
new = '    "okf-parser[graphql]==0.43.0",\n'
if text.count(old) != 1:
    raise RuntimeError("expected exactly one okf-parser 0.42.8 dependency anchor")
path.write_text(text.replace(old, new), encoding="utf-8")
