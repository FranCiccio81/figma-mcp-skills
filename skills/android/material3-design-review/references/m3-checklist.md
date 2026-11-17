# Material 3 and Android checklist

## Window size classes (width)

| Class | Width | Typical navigation |
|---|---|---|
| Compact | < 600 dp | Navigation bar (3 to 5 destinations) |
| Medium | 600 to 840 dp | Navigation rail |
| Expanded | 840 to 1200 dp | Navigation rail or permanent drawer, two panes |
| Large | 1200 to 1600 dp | Rail or drawer, two or three panes |
| Extra-large | ≥ 1600 dp | Desktop-like layouts |

Height classes: compact < 480 dp, medium 480 to 900 dp, expanded ≥ 900 dp.

## Color role pairs to check for contrast

primary / onPrimary, primaryContainer / onPrimaryContainer, secondary / onSecondary,
surface / onSurface, surfaceVariant (or surface container levels) / onSurfaceVariant,
error / onError, inverseSurface / inverseOnSurface.

## iOS to Android adaptation

| iOS pattern | Android equivalent |
|---|---|
| Back chevron with previous title | Top app bar navigation icon, system back and predictive back |
| Tab bar | Navigation bar (compact) or rail (medium and larger) |
| Action sheet | Bottom sheet or menu |
| Segmented control | Segmented buttons, tabs or filter chips |
| Swipe actions in lists | Swipe with visible alternative (menu or long press) |
| SF Symbols | Material Symbols or project icons |
