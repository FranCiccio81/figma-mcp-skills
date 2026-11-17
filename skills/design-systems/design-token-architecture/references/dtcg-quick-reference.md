# DTCG 2025.10 quick reference

Summary for orientation only. The normative text is the Design Tokens Format Module 2025.10 at
https://www.designtokens.org/TR/2025.10/ ; check it before generating files for production.

## Token and group anatomy

```json
{
  "color": {
    "$type": "color",
    "brand": {
      "blue-600": {
        "$value": { "colorSpace": "srgb", "components": [0, 0.34, 1], "hex": "#0057ff" },
        "$description": "Primitive. Do not use directly in components."
      }
    },
    "action": {
      "primary": {
        "default": { "$value": "{color.brand.blue-600}" },
        "hover": { "$value": "{color.brand.blue-700}", "$deprecated": false }
      }
    }
  },
  "space": {
    "$type": "dimension",
    "inset-md": { "$value": { "value": 16, "unit": "px" } }
  },
  "motion": {
    "duration-fast": { "$type": "duration", "$value": { "value": 150, "unit": "ms" } }
  }
}
```

- Properties starting with `$` are reserved by the spec; other keys are token or group names.
- `$type` can be set on a group and is inherited by its tokens.
- Aliases use curly braces with the dot path: `{color.brand.blue-600}`.
- `$extensions` holds vendor data (for example a Figma variable ID) under a reverse-domain key.
- `$deprecated` can be `true` or a string explaining the replacement.

## Types

Basic: `color`, `dimension`, `fontFamily`, `fontWeight`, `duration`, `cubicBezier`, `number`.
Composite: `strokeStyle`, `border`, `transition`, `shadow`, `gradient`, `typography`.

## Modes and themes

The Resolver module describes how token sets combine for contexts such as light and dark themes.
Keep primitives in one set and put semantic overrides per mode in separate sets.

## Mapping checklist

| From | To DTCG |
|---|---|
| Tokens Studio `value`, `type` | `$value`, `$type`; check type names (for example `spacing` becomes `dimension`) |
| Style Dictionary v3 `value` | Style Dictionary v4 reads DTCG `$value` natively; confirm the project's version |
| Figma variable collection modes | One token set per mode, combined by the resolver |
| Hex strings | Color module object with `colorSpace` and `components`; keep `hex` as fallback |
