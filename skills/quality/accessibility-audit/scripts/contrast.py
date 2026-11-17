#!/usr/bin/env python3
"""WCAG 2.x contrast ratio calculator (no dependencies, no network).

Usage:
  python3 contrast.py "#9CA3AF" "#FFFFFF"
  python3 contrast.py 6B7280 FFFFFF --large

Prints the ratio and the pass or fail status for normal text (4.5:1),
large text (3:1) and non-text UI components (3:1).
"""

from __future__ import annotations

import argparse
import sys


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def parse_hex(color: str) -> tuple[float, float, float]:
    text = color.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError(f"Not a 3 or 6 digit hex color: {color!r}")
    return tuple(int(text[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(color: str) -> float:
    r, g, b = (_channel(c) for c in parse_hex(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted((relative_luminance(foreground), relative_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def evaluate(foreground: str, background: str) -> dict:
    ratio = contrast_ratio(foreground, background)
    return {
        "ratio": round(ratio, 2),
        "normal_text_aa": ratio >= 4.5,
        "large_text_aa": ratio >= 3.0,
        "ui_component_aa": ratio >= 3.0,
        "normal_text_aaa": ratio >= 7.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WCAG contrast ratio")
    parser.add_argument("foreground")
    parser.add_argument("background")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.foreground, args.background)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"Contrast {args.foreground} on {args.background}: {result['ratio']}:1")
    for key in ("normal_text_aa", "large_text_aa", "ui_component_aa", "normal_text_aaa"):
        print(f"  {key:16} {'PASS' if result[key] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
