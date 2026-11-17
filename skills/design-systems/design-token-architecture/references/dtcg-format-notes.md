# DTCG 2025.10: format notes

Summary written for this skill from the Design Tokens Format Module 2025.10 (https://www.designtokens.org/tr/2025.10/format/), verified on 2026-11-17. The specification is authoritative; re-read it for any edge case.

## Tokens and groups

* An object with `$value` is a token; an object without `$value` is a group. An object cannot be both.
* `$type` on a token, or inherited from the nearest ancestor group, or from the aliased token. Tools must not guess a type from the value.
* `$description` (string), `$deprecated` (boolean or explanation string), `$extensions` (vendor data, reverse-domain keys, must be preserved by tools).
* `$root`: reserved name for a group's base token, for example `color.accent.$root`.
* `$extends`: a group inherits another group by deep merge; local definitions win.

## Names

* Case-sensitive JSON strings; must not start with `$`; must not contain `{`, `}` or `.`.

## References

* Curly braces `{color.blue.500}` reference a whole token and resolve to its `$value`.
* `$ref` with a JSON Pointer (for example `#/color/blue/$value/components/0`) can reference any property.
* Circular references (aliases, `$extends`, `$ref`) are errors.

## Types

| Type | Value shape |
|---|---|
| `color` | object defined by the Color module: `colorSpace`, `components`, optional `alpha` and `hex` |
| `dimension` | `{ "value": 16, "unit": "px" }`, unit `px` or `rem`, unit required even for 0 |
| `fontFamily` | string or array of strings in preference order |
| `fontWeight` | number 1 to 1000 or a named alias such as `bold` |
| `duration` | `{ "value": 200, "unit": "ms" }`, unit `ms` or `s` |
| `cubicBezier` | `[x1, y1, x2, y2]`, x values in 0..1 |
| `number` | JSON number |
| `strokeStyle` | keyword (`solid`, `dashed`, ...) or `{ dashArray, lineCap }` |
| `border` | `{ color, width, style }` |
| `transition` | `{ duration, delay, timingFunction }` |
| `shadow` | one shadow object or an array: `color`, `offsetX`, `offsetY`, `blur`, `spread`, optional `inset` |
| `gradient`, `typography` | composite types, see the specification |

## Files

* JSON; media type `application/design-tokens+json` preferred (`application/json` accepted).
* Extensions `.tokens` or `.tokens.json`.

## Example

```json
{
  "color": {
    "$type": "color",
    "blue": {
      "600": { "$value": { "colorSpace": "srgb", "components": [0, 0.341, 1], "hex": "#0057ff" } }
    }
  },
  "semantic": {
    "action": {
      "primary": {
        "background": {
          "$type": "color",
          "$value": "{color.blue.600}",
          "$description": "Fill of the primary call to action."
        }
      }
    }
  },
  "space": {
    "$type": "dimension",
    "inset": { "md": { "$value": { "value": 16, "unit": "px" } } }
  }
}
```

## Themes

The Resolver module (https://www.designtokens.org/tr/2025.10/resolver/) describes how sets of token files combine for contexts such as light and dark modes. Resolver documents declare `version: "2025.10"`.
