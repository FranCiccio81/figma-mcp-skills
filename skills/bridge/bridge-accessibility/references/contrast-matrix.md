# Contrast of key Bridge token pairs (computed)

Computed on 2026-11-17 with the WCAG relative luminance formula from the SQ Light and SQ Dark values in `bridge-foundations.md` (snapshot of 12 November 2026). Values are rounded to two decimals and verified by `tools/tests/test_reference_content.py`. Recompute when live Figma values differ, and for PF and Default themes.

Thresholds: normal text 4.5:1 (AAA 7:1), large text and UI components 3:1.

## SQ Light

| Foreground token | Hex | on surface `#ffffff` | on canvas `#f7f9fd` | Normal text AA |
|---|---|---|---|---|
| text/neutral/strong | #121212 | 18.73 | 17.77 | pass (AAA) |
| text/neutral/default | #323232 | 12.82 | 12.16 | pass (AAA) |
| text/neutral/muted | #6a7079 | 4.99 | 4.74 | pass |
| text/neutral/subtle | #5d6b98 | 5.22 | 4.95 | pass |
| text/link | #004fc4 | 7.20 | 6.83 | pass |
| data/up | #059669 | 3.77 | 3.58 | **fail** (large text and icons only) |
| data/down | #fb2c36 | 3.81 | 3.61 | **fail** (large text and icons only) |
| border/default | #dcdfea | 1.33 | 1.26 | not for essential boundaries |
| border/strong | #717784 | 4.49 | 4.26 | passes 3:1 for UI |
| border/focus | #146af0 | 4.83 | 4.58 | passes 3:1 for focus |

| Background token (primary) | Hex | White text on it |
|---|---|---|
| action/product primary | #323232 | 12.82 |
| action/trade/buy primary | #146af0 | 4.83 |
| action/trade/sell primary | #ec0000 | 4.60 |
| action/brand primary | #fa5b35 | 3.18 (fails 4.5 for normal text) |
| action/destructive primary | #f95959 | 3.18 (fails 4.5 for normal text) |

The on-primary text token values are not in the snapshot; the white-text column is a check to run, not a statement about the actual token.

## SQ Dark

| Foreground token | Hex | on surface `#323232` | on canvas `#121212` | Normal text AA |
|---|---|---|---|---|
| text/neutral/strong | #ffffff | 12.82 | 18.73 | pass |
| text/neutral/default | #f6f7f9 | 11.96 | 17.48 | pass |
| text/neutral/muted | #eef0f3 | 11.23 | 16.41 | pass |
| text/neutral/subtle | #b9c0d4 | 7.05 | 10.31 | pass |
| text/link | #93baf8 | 6.48 | 9.47 | pass |
| data/up | #10b978 | 5.03 | 7.34 | pass |
| data/down | #ff6568 | 4.47 | 6.52 | **fail on surface** (passes on canvas) |
| border/default | #4a5578 | 1.75 | 2.55 | **fails 3:1** for essential boundaries |
| border/strong | #525866 | 1.80 | 2.63 | **fails 3:1** for essential boundaries |
| border/focus | #4388f3 | 3.70 | 5.40 | passes 3:1 |
