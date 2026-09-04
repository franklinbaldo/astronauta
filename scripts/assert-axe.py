#!/usr/bin/env python3
"""Run axe-core in the same Chromium used by the visual workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--axe-source", type=Path, required=True)
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    chrome = os.environ.get("CHROME")
    if not chrome:
        raise SystemExit("CHROME must point to the browser executable")
    if not args.axe_source.is_file():
        raise SystemExit(f"axe source not found: {args.axe_source}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chrome,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        response = page.goto(args.url, wait_until="networkidle")
        if response is None or not response.ok:
            status = response.status if response is not None else "no response"
            raise SystemExit(f"{args.url} did not load successfully: {status}")

        page.add_script_tag(path=str(args.axe_source))
        result = page.evaluate("async () => await axe.run(document)")
        serious = [
            item for item in result.get("violations", [])
            if item.get("impact") in {"serious", "critical"}
        ]
        payload = {
            "url": args.url,
            "viewport": {"width": args.width, "height": args.height},
            "httpStatus": response.status,
            "violationCount": len(result.get("violations", [])),
            "seriousOrCriticalCount": len(serious),
            "violations": result.get("violations", []),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        browser.close()

    if serious:
        for item in serious:
            print(f"FAIL: {item.get('impact')}: {item.get('id')}: {item.get('help')}")
        return 1
    print(f"OK: axe sem violações sérias ou críticas em {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
