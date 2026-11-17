#!/usr/bin/env python3
"""Check that external URLs cited by skills and the source registry still resolve.

Network access is required, so this check runs on a schedule in CI and never blocks
a pull request. Only domains declared in the source registry are contacted.

Usage:
  python3 scripts/check_links.py            # report broken links, exit 1 if any
  python3 scripts/check_links.py --timeout 15
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skillslib import REPO_ROOT, SKILLS_DIR, SOURCE_REGISTRY, load_source_registry  # noqa: E402

URL_RE = re.compile(r"https?://[^\s)>\]`\"'|]+")
SKIP_HOSTS = {"127.0.0.1", "localhost", "mcp.figma.com"}
USER_AGENT = "figma-mcp-skills-link-check/1.0 (+https://github.com/FranCiccio81/figma-mcp-skills)"


def collect_urls() -> dict[str, set[str]]:
    _, domains = load_source_registry()
    files = [SOURCE_REGISTRY, *SKILLS_DIR.rglob("*.md")]
    urls: dict[str, set[str]] = {}
    for path in files:
        for url in URL_RE.findall(path.read_text(encoding="utf-8")):
            url = url.rstrip(".,;:")
            host = (urlparse(url).hostname or "").lower()
            if "<" in url or host in SKIP_HOSTS:
                continue
            if not any(host == d or host.endswith("." + d) for d in domains):
                continue
            urls.setdefault(url, set()).add(str(path.relative_to(REPO_ROOT)))
    return urls


def check(url: str, timeout: float) -> str | None:
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status < 400:
                    return None
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 429):
                continue
            if exc.code in (403, 429):
                return None  # bot protection or rate limit: not evidence of a broken link
            return f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return f"UNREACHABLE {type(exc).__name__}: {exc}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    urls = collect_urls()
    broken = unreachable = 0
    for url, where in sorted(urls.items()):
        problem = check(url, args.timeout)
        if not problem:
            continue
        if problem.startswith("UNREACHABLE"):
            unreachable += 1
            print(f"UNREACHABLE {url} ({problem[12:]})")
        else:
            broken += 1
            print(f"BROKEN {url} ({problem}) in {', '.join(sorted(where))}")
    ok = len(urls) - broken - unreachable
    print(f"{len(urls)} URLs: {ok} ok, {broken} broken, {unreachable} unreachable (network or proxy, not conclusive)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
