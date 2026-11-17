<!-- evaluation: executed -->
# Evaluation results

## 2026-11-17, eval case 1 (contrast of the Input component colors)

Executed with `scripts/contrast.py` and covered by `tests/test_skill_scripts.py`.

| Pair | Computed ratio | Expected | Result |
|---|---|---|---|
| #9CA3AF on #FFFFFF | 2.54:1 | fails text and UI (3:1) | pass |
| #D1D5DB on #FFFFFF | 1.47:1 | fails 1.4.11 as a field boundary | pass |
| #111827 on #FFFFFF | 17.74:1 | passes | pass |
| #3B82F6 on #FFFFFF | 3.68:1 | passes 3:1 for focus indicator, fails 4.5:1 for text | pass |

Finding carried into the repository: `.claude/CLAUDE.md` stated 2.85:1 for Grey/400; corrected to 2.54:1.
Eval case 2 (Figma-only audit) not executed.
