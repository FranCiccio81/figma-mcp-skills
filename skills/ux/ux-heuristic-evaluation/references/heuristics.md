# Heuristics and severity scale

Paraphrased from Jakob Nielsen's ten usability heuristics (Nielsen Norman Group). Read the
original articles for full explanations.

| # | Heuristic | What to look for |
|---|---|---|
| H1 | Visibility of system status | Feedback after actions, progress for waits, current location |
| H2 | Match with the real world | User vocabulary, natural order, familiar metaphors, local formats (dates, currency) |
| H3 | User control and freedom | Undo, cancel, back, exits from flows, no traps |
| H4 | Consistency and standards | Same words and patterns for the same things, platform conventions |
| H5 | Error prevention | Constraints, confirmations for destructive actions, good defaults |
| H6 | Recognition over recall | Visible options, remembered context, no codes to memorise |
| H7 | Flexibility and efficiency | Shortcuts for experts, defaults for novices, personalisation |
| H8 | Aesthetic and minimalist design | Only relevant information, clear hierarchy |
| H9 | Help users recover from errors | Plain-language messages, cause, solution, preserved input |
| H10 | Help and documentation | Contextual, task-oriented, searchable |

## Severity scale (0 to 4)

| Score | Meaning | Typical action |
|---|---|---|
| 0 | Not a usability problem | None |
| 1 | Cosmetic | Fix if time allows |
| 2 | Minor | Low priority |
| 3 | Major | High priority, fix before release |
| 4 | Catastrophic | Blocks task completion or causes harm; fix before release |

Rate using three factors: frequency (how often it occurs), impact (how hard to overcome) and
persistence (once or every time). In financial products, raise severity one level when the issue
can cause a wrong transaction, a missed legal disclosure or loss of money.
