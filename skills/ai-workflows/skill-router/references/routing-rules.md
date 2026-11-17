# Routing rules

The machine-readable table is [routing-table.json](routing-table.json); `scripts/route.py`
applies it deterministically. Agents can apply the same rules by reading this page.

1. **Project context first.** Read `CLAUDE.md`, `.claude/CLAUDE.md` and `rules/` before any skill.
2. **Platform detection.** Keywords in the request (for example "iOS", "SwiftUI", "Android",
   "Compose", "React", "web") or repository markers. Apple platforms share the Apple skills.
3. **Intent detection.** Each intent has keywords and either platform-neutral skills or
   platform-specific skills. Platform-specific skills are added only for detected platforms.
4. **Implementation implies platform design.** When implementing UI for a platform, include the
   platform design review skill of that platform.
5. **Accessibility is platform-specific.** "Accessible" adds `apple-accessibility`,
   `android-accessibility` or `accessibility-audit` depending on the platform.
6. **Exclusions are explicit.** List skills that were not activated because of the platform.
7. **Order by phase:** context, product, UX, design systems, platform design, implementation, quality.
8. **Precedence for conflicts:** safety and law, project constraints, official platform guidance,
   project design system, reusable skills, community practices.

## Worked example

Request: "Design and implement an accessible banking onboarding flow for iOS."

| Step | Skill | Why |
|---|---|---|
| 0 | Project `CLAUDE.md` and rules | Project design system and constraints (precedence 2 and 4) |
| 1 | product-requirements | New flow: problem, scope, success indicators, compliance requirements |
| 2 | interaction-design-spec | Onboarding flow states and transitions |
| 3 | apple-hig-review | iOS conventions for structure and components |
| 4 | swiftui-implementation | Implementation, including previews and tests |
| 5 | apple-accessibility | Explicit accessibility requirement (VoiceOver, Dynamic Type) |

Excluded: Android skills (platform not targeted), web engineering skills (platform not targeted),
enterprise design system references not used by the project.
