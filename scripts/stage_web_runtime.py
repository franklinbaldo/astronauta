#!/usr/bin/env python3
"""Stage Astro standalone output inside the Python package before wheel build."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dist"
TARGET = ROOT / "src" / "astronauta" / "_web"


def main() -> int:
    entry = SOURCE / "server" / "entry.mjs"
    if not entry.is_file():
        raise SystemExit("dist/server/entry.mjs not found; run `bun run build` first")

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)

    packaged_entry = TARGET / "server" / "entry.mjs"
    if not packaged_entry.is_file():
        raise SystemExit("staged runtime is missing server/entry.mjs")
    print(f"staged Astro runtime at {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
