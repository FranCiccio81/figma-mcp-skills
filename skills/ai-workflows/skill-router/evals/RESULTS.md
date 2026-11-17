<!-- evaluation: automated -->
# Evaluation results

## 2026-11-17

Both eval cases are executed automatically by `tests/test_skill_scripts.py` through
`scripts/route.py`:

| Case | Assertion | Result |
|---|---|---|
| 1. Accessible banking onboarding flow for iOS | product-requirements, interaction-design-spec, apple-hig-review, swiftui-implementation, apple-accessibility selected in phase order; no Android skill | pass |
| 2. "Implement this screen." | Asks for the platform; no implementation skill selected | pass |

Additional automated cases: Android-only request excludes Apple skills; Figma link routes
`figma-design-context` first; iOS and Android request includes both branches.
