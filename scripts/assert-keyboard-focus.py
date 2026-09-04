#!/usr/bin/env python3
"""Verify keyboard reachability and perceptible focus in a real browser."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

SELECTOR = "a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex='-1'])"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chrome = os.environ.get("CHROME")
    if not chrome:
        raise SystemExit("CHROME must point to the browser executable")

    failures: list[str] = []
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

        controls = page.evaluate(
            """selector => {
              const visible = (el) => {
                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                  && rect.width > 0 && rect.height > 0 && !el.hidden;
              };
              const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true';
              const found = [...document.querySelectorAll(selector)].filter((el) => visible(el) && enabled(el));
              found.forEach((el, index) => el.dataset.keyboardAuditId = `control-${index + 1}`);
              return found.map((el) => ({
                id: el.dataset.keyboardAuditId,
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
                ariaLabel: el.getAttribute('aria-label'),
                href: el.getAttribute('href')
              }));
            }""",
            SELECTOR,
        )

        baselines = page.evaluate(
            """() => Object.fromEntries([...document.querySelectorAll('[data-keyboard-audit-id]')].map((el) => {
              const s = getComputedStyle(el);
              return [el.dataset.keyboardAuditId, {
                borderColor: s.borderColor,
                backgroundColor: s.backgroundColor,
                boxShadow: s.boxShadow
              }];
            }))"""
        )
        page.evaluate("() => document.activeElement instanceof HTMLElement && document.activeElement.blur()")

        reached: set[str] = set()
        sequence: list[dict[str, object]] = []
        focus_failures: list[str] = []
        max_steps = max(4, len(controls) * 2 + 4)

        for _ in range(max_steps):
            page.keyboard.press("Tab")
            state = page.evaluate(
                """() => {
                  const el = document.activeElement;
                  if (!el || !el.dataset.keyboardAuditId) return {id: null};
                  const s = getComputedStyle(el);
                  return {
                    id: el.dataset.keyboardAuditId,
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
                    focusVisible: el.matches(':focus-visible'),
                    outlineStyle: s.outlineStyle,
                    outlineWidth: s.outlineWidth,
                    outlineColor: s.outlineColor,
                    boxShadow: s.boxShadow,
                    borderColor: s.borderColor,
                    backgroundColor: s.backgroundColor
                  };
                }"""
            )
            control_id = state.get("id")
            if not control_id or control_id in reached:
                if len(reached) == len(controls):
                    break
                continue

            baseline = baselines.get(control_id, {})
            outline = state.get("outlineStyle") != "none" and state.get("outlineWidth") not in {"0px", None}
            style_change = (
                state.get("boxShadow") not in {"none", None}
                or state.get("borderColor") != baseline.get("borderColor")
                or state.get("backgroundColor") != baseline.get("backgroundColor")
            )
            perceptible = bool(state.get("focusVisible")) and bool(outline or style_change)
            state["perceptibleFocus"] = perceptible
            sequence.append(state)
            reached.add(str(control_id))
            if not perceptible:
                focus_failures.append(str(control_id))
            if len(reached) == len(controls):
                break

        missing = [control for control in controls if control["id"] not in reached]
        if missing:
            failures.append(f"{len(missing)} controle(s) visível(is) não foram alcançados por Tab")
        if focus_failures:
            failures.append(f"{len(focus_failures)} controle(s) alcançados não mostraram foco perceptível")

        result = {
            "url": args.url,
            "viewport": {"width": args.width, "height": args.height},
            "httpStatus": response.status,
            "expectedCount": len(controls),
            "reachedCount": len(reached),
            "controls": controls,
            "sequence": sequence,
            "missingControls": missing,
            "focusFailures": focus_failures,
            "failures": failures,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        browser.close()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: Tab alcançou {len(reached)}/{len(controls)} controles visíveis com foco perceptível")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
