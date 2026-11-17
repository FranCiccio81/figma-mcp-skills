# Liquid Glass in SwiftUI (26-series SDKs)

APIs below were checked on 2026-11-17 against developer.apple.com (SwiftUI reference). Recheck
for the SDK in use.

| API | Purpose |
|---|---|
| `glassEffect(_:in:)` | Applies Liquid Glass to a view; defaults to the `regular` variant in a capsule shape |
| `Glass.regular`, `Glass.clear` | Variants; `clear` only over visually rich backgrounds |
| `Glass.interactive(_:)` | Makes the glass react to touch and pointer |
| `GlassEffectContainer` | Groups glass views so they render and morph together |
| `glassEffectID(_:in:)` | Identity for morphing transitions inside a container |
| `.buttonStyle(.glass)`, `.buttonStyle(.glassProminent)` | Glass button styles; prominent for the primary action |

```swift
struct FloatingControls: View {
    @Namespace private var glass

    var body: some View {
        if #available(iOS 26, macOS 26, *) {
            GlassEffectContainer {
                HStack {
                    Button("Edit", systemImage: "pencil") { }
                        .buttonStyle(.glass)
                    Button("Share", systemImage: "square.and.arrow.up") { }
                        .buttonStyle(.glassProminent)
                }
            }
        } else {
            HStack {
                Button("Edit", systemImage: "pencil") { }
                Button("Share", systemImage: "square.and.arrow.up") { }
                    .buttonStyle(.borderedProminent)
            }
            .padding()
            .background(.regularMaterial, in: Capsule())
        }
    }
}
```

Rules:

- Standard `TabView`, toolbars, navigation bars and sheets adopt the new appearance when built
  with the new SDK; do not recreate them by hand.
- Do not stack glass on glass; do not apply glass to content such as lists or cards.
- Test with Reduce Transparency, Increase Contrast and Reduce Motion.
