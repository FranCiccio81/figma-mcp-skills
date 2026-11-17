# Apple platform matrix

Paraphrased orientation table. Check the linked HIG pages for the current wording.

| Platform | Primary structure | Input | Default and minimum control size (HIG, Accessibility) | Notes |
|---|---|---|---|---|
| iOS | Tab bar for top-level areas, navigation stack for hierarchy, sheets for focused tasks | Touch, VoiceOver, keyboard optional | 44 × 44 pt default, 28 × 28 pt minimum | No back button on root views; large titles where useful |
| iPadOS | Sidebar and split views, tab bar that can become a sidebar, multiple windows | Touch, Apple Pencil, pointer, keyboard | 44 × 44 pt default, 28 × 28 pt minimum | Adapt to size classes and window resizing; support keyboard shortcuts |
| macOS | Windows, menu bar with all commands, toolbars, sidebars, inspectors | Pointer, keyboard | 28 × 28 pt default, 20 × 20 pt minimum | Every command reachable from the menu bar; standard shortcuts |
| watchOS | Short, glanceable views, vertical pagination, complications | Touch, Digital Crown | 44 × 44 pt default, 28 × 28 pt minimum | Sessions measured in seconds |
| visionOS | Windows, volumes, immersive spaces | Eyes and hands (indirect), direct touch | 60 × 60 pt default, 28 × 28 pt minimum | Keep content in comfortable field of view; hover effects on interactive elements |
| tvOS | Focus-driven layouts | Siri Remote focus engine | 66 × 66 pt default, 56 × 56 pt minimum | Design for distance |

## Contrast guidance (HIG, Accessibility)

Text up to 17 pt needs at least 4.5:1, text of 18 pt and above or bold text at least 3:1. When the
default appearance cannot meet it, provide a higher contrast scheme under Increase Contrast.

## Liquid Glass checklist (26-series releases)

- Applied to controls and navigation (tab bars, toolbars, sidebars, floating buttons), not content.
- No glass stacked on glass; group nearby glass elements so they render together.
- `regular` variant by default; `clear` only over visually rich media with a dimming layer if needed.
- Legible under Reduce Transparency, Increase Contrast and in both appearances.
- Custom components re-tested after adopting the system appearance.
