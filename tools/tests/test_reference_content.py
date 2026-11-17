"""Checks facts embedded in skill content that can be verified mechanically."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class ContrastFacts(unittest.TestCase):
    """Ratios quoted in skills and corrected documents (WCAG 2.x relative luminance formula)."""

    def test_grey_400_on_white(self):
        self.assertAlmostEqual(contrast("9CA3AF", "FFFFFF"), 2.54, places=2)

    def test_grey_500_on_white_passes_aa(self):
        ratio = contrast("6B7280", "FFFFFF")
        self.assertAlmostEqual(ratio, 4.83, places=2)
        self.assertGreaterEqual(ratio, 4.5)


class DtcgExample(unittest.TestCase):
    """The DTCG example in design-token-architecture must follow the 2025.10 rules it teaches."""

    def setUp(self):
        text = (ROOT / "skills/design-systems/design-token-architecture/references/dtcg-format-notes.md").read_text()
        block = re.search(r"## Example\s+```json\n(.*?)```", text, re.S).group(1)
        self.tokens = json.loads(block)

    def walk(self, node, path=(), inherited=None):
        if isinstance(node, dict) and "$value" in node:
            yield path, node, node.get("$type", inherited)
            return
        if isinstance(node, dict):
            group_type = node.get("$type", inherited)
            for key, child in node.items():
                if not key.startswith("$"):
                    self.assertNotRegex(key, r"[{}.]", f"invalid token name {key}")
                    yield from self.walk(child, path + (key,), group_type)

    def resolve(self, ref):
        node = self.tokens
        for part in ref.strip("{}").split("."):
            node = node[part]
        return node

    def test_every_token_has_a_type_and_valid_aliases(self):
        found = list(self.walk(self.tokens))
        self.assertGreater(len(found), 0)
        for path, token, token_type in found:
            value = token["$value"]
            if isinstance(value, str) and value.startswith("{"):
                target = self.resolve(value)
                self.assertIn("$value", target, f"{'.'.join(path)} aliases a group")
                continue
            self.assertIsNotNone(token_type, f"{'.'.join(path)} has no resolvable $type")
            if token_type == "dimension":
                self.assertIn(value["unit"], ("px", "rem"))
            if token_type == "color":
                self.assertIn("colorSpace", value)
                self.assertIn("components", value)


if __name__ == "__main__":
    unittest.main()
