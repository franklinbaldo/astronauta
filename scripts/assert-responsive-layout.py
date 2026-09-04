#!/usr/bin/env python3
"""Measure narrow-layout containment in a real browser and fail on global overflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--must-fit", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chrome = os.environ.get("CHROME")
    if not chrome:
        raise SystemExit("CHROME must point to the browser executable")

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

        metrics = page.evaluate(
            """() => ({
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              documentClientWidth: document.documentElement.clientWidth,
              documentScrollWidth: document.documentElement.scrollWidth,
              bodyScrollWidth: document.body.scrollWidth
            })"""
        )
        elements: dict[str, dict[str, float | bool]] = {}
        failures: list[str] = []

        if metrics["documentScrollWidth"] > metrics["documentClientWidth"]:
            failures.append(
                "documento mais largo que a janela: "
                f"{metrics['documentScrollWidth']}px > {metrics['documentClientWidth']}px"
            )

        for selector in args.must_fit:
            locator = page.locator(selector).first
            if locator.count() == 0:
                failures.append(f"elemento obrigatório não encontrado: {selector}")
                continue
            box = locator.bounding_box()
            if box is None:
                failures.append(f"elemento obrigatório não está visível: {selector}")
                continue
            right = box["x"] + box["width"]
            fits = box["x"] >= -0.5 and right <= metrics["innerWidth"] + 0.5
            elements[selector] = {
                "x": round(box["x"], 2),
                "width": round(box["width"], 2),
                "right": round(right, 2),
                "fitsViewport": fits,
            }
            if not fits:
                failures.append(
                    f"{selector} sai da janela: x={box['x']:.1f}, right={right:.1f}, "
                    f"viewport={metrics['innerWidth']}"
                )

        result = {
            "url": args.url,
            "viewport": {"width": args.width, "height": args.height},
            "metrics": metrics,
            "elements": elements,
            "failures": failures,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        browser.close()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(
        f"OK: {args.url} cabe em {metrics['documentClientWidth']}px "
        f"(scrollWidth={metrics['documentScrollWidth']}px)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
