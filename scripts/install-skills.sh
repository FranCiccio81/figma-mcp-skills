#!/usr/bin/env bash
# Install skills from this repository into an agent skills folder.
#
# Claude Code discovers skills one level deep (<target>/<skill-name>/SKILL.md), so this script
# flattens skills/<domain>/<skill-name>/ into <target>/<skill-name>/ using symbolic links
# (default) or copies (--copy, for Windows or for shipping a snapshot).
#
# No network access, no execution of skill content.
#
# Examples:
#   scripts/install-skills.sh --target ~/.claude/skills                      # all skills, user scope
#   scripts/install-skills.sh --target ../my-app/.claude/skills --domain apple --domain quality
#   scripts/install-skills.sh --target .claude/skills --skill skill-router --skill figma-design-context
#   scripts/install-skills.sh --list
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

target=""
mode="link"
dry_run=0
force=0
list_only=0
domains=()
names=()

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'
Options:
  --target DIR    destination folder (for example ~/.claude/skills or <project>/.claude/skills)
  --domain NAME   install only this domain (repeatable)
  --skill NAME    install only this skill (repeatable)
  --copy          copy files instead of creating symbolic links
  --force         replace an existing entry with the same name
  --dry-run       show what would happen
  --list          list available skills and exit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:?--target needs a directory}"; shift 2 ;;
    --domain) domains+=("${2:?--domain needs a name}"); shift 2 ;;
    --skill) names+=("${2:?--skill needs a name}"); shift 2 ;;
    --copy) mode="copy"; shift ;;
    --force) force=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    --list) list_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

mapfile -t skill_dirs < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -type d ! -name '.*' | sort)

contains() {
  local needle="$1"; shift
  local item
  for item in "$@"; do [[ "$item" == "$needle" ]] && return 0; done
  return 1
}

selected=()
for dir in "${skill_dirs[@]}"; do
  [[ -f "$dir/SKILL.md" ]] || continue
  name="$(basename "$dir")"
  domain="$(basename "$(dirname "$dir")")"
  if [[ ${#domains[@]} -gt 0 ]] && ! contains "$domain" "${domains[@]}"; then continue; fi
  if [[ ${#names[@]} -gt 0 ]] && ! contains "$name" "${names[@]}"; then continue; fi
  selected+=("$dir")
done

if [[ $list_only -eq 1 ]]; then
  for dir in "${selected[@]}"; do
    printf '%-16s %s\n' "$(basename "$(dirname "$dir")")" "$(basename "$dir")"
  done
  exit 0
fi

[[ -n "$target" ]] || { echo "Missing --target (see --help)" >&2; exit 2; }
[[ ${#selected[@]} -gt 0 ]] || { echo "No skill matches the filters" >&2; exit 1; }

if [[ ${#names[@]} -gt 0 ]]; then
  for wanted in "${names[@]}"; do
    found=0
    for dir in "${selected[@]}"; do [[ "$(basename "$dir")" == "$wanted" ]] && found=1; done
    [[ $found -eq 1 ]] || { echo "Unknown skill: $wanted" >&2; exit 1; }
  done
fi

[[ $dry_run -eq 1 ]] || mkdir -p "$target"

installed=0
for dir in "${selected[@]}"; do
  name="$(basename "$dir")"
  dest="$target/$name"
  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ $force -eq 0 ]]; then
      echo "skip   $name (already exists at $dest; use --force to replace)"
      continue
    fi
    if [[ ! -L "$dest" && ! -f "$dest/SKILL.md" ]]; then
      echo "refuse $name ($dest is not a skill folder or link; remove it manually)" >&2
      continue
    fi
    [[ $dry_run -eq 1 ]] || rm -rf -- "$dest"
  fi
  if [[ $dry_run -eq 1 ]]; then
    echo "would $mode $name -> $dest"
  elif [[ "$mode" == "copy" ]]; then
    cp -R "$dir" "$dest"
    echo "copied $name"
  else
    ln -s "$dir" "$dest"
    echo "linked $name"
  fi
  installed=$((installed + 1))
done

echo "$installed skill(s) processed into $target"
