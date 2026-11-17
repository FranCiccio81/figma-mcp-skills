#!/usr/bin/env bash
# Install skills from this library into a project (or user) skills folder.
#
# Skills are linked flat, as Agent Skills clients expect: <target>/<skill-name>/SKILL.md
#
# Usage:
#   tools/install.sh <target-skills-dir> [--copy] [--force] [--domain <d>]... [--skill <name>]... [--include-project]
#
# Examples:
#   tools/install.sh ~/my-app/.claude/skills --domain apple --domain ux
#   tools/install.sh ~/.claude/skills --skill skill-router --skill accessibility-audit
#
# Safety:
#   * never overwrites an existing entry unless --force is given
#   * project-scoped skills (metadata scope: project) are skipped unless --include-project
#   * runs nothing from the skills themselves
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=""; MODE="link"; FORCE=0; INCLUDE_PROJECT=0
DOMAINS=(); NAMES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy) MODE="copy" ;;
    --force) FORCE=1 ;;
    --include-project) INCLUDE_PROJECT=1 ;;
    --domain) DOMAINS+=("$2"); shift ;;
    --skill) NAMES+=("$2"); shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) if [[ -z "$TARGET" ]]; then TARGET="$1"; else echo "unexpected argument: $1" >&2; exit 2; fi ;;
  esac
  shift
done

[[ -n "$TARGET" ]] || { echo "usage: tools/install.sh <target-skills-dir> [options]" >&2; exit 2; }
mkdir -p "$TARGET"

installed=0; skipped=0
while IFS= read -r skill_md; do
  dir="$(dirname "$skill_md")"
  name="$(basename "$dir")"
  domain="$(basename "$(dirname "$dir")")"
  if [[ ${#DOMAINS[@]} -gt 0 && ! " ${DOMAINS[*]} " =~ " ${domain} " ]]; then continue; fi
  if [[ ${#NAMES[@]} -gt 0 && ! " ${NAMES[*]} " =~ " ${name} " ]]; then continue; fi
  if [[ $INCLUDE_PROJECT -eq 0 ]] && grep -qE '^\s*scope:\s*project' "$skill_md"; then
    echo "skip (project-scoped): $name"; skipped=$((skipped+1)); continue
  fi
  dest="$TARGET/$name"
  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ $FORCE -eq 0 ]]; then echo "skip (exists, use --force): $dest"; skipped=$((skipped+1)); continue; fi
    rm -rf "$dest"
  fi
  if [[ "$MODE" == "copy" ]]; then cp -R "$dir" "$dest"; else ln -s "$dir" "$dest"; fi
  echo "$MODE: $name -> $dest"; installed=$((installed+1))
done < <(find "$ROOT/skills" -mindepth 3 -maxdepth 3 -name SKILL.md | sort)

echo "done: $installed installed, $skipped skipped"
