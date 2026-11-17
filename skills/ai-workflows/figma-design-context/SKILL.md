---
name: figma-design-context
description: >-
  Extracts reliable design context from Figma through the Figma MCP server: verifies which server
  and tools are actually available, parses file and node IDs, chooses a size-aware call strategy
  (metadata, design context per section, screenshot, variables, Code Connect), handles assets and
  warnings, and falls back transparently when MCP is unavailable. Use when any task needs to read a
  Figma design (implementation, specs, token mapping, QA), when given a figma.com link or a desktop
  selection, or when Figma MCP calls fail or return truncated output. Do not use for writing to the
  Figma canvas (use the official figma-use skill).
license: MIT
compatibility: "Needs the Figma MCP server (remote https://mcp.figma.com/mcp or desktop http://127.0.0.1:3845/mcp) for live data; otherwise works from exports."
metadata:
  version: "1.1.0"
  domain: ai-workflows
  status: stable
  trust: official-derived
  sources: "DOC-FIGMA-MCP,REPO-FIGMA-MCP-GUIDE"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Figma design context

Never describe a design you have not read. If the MCP call did not return it, it is unknown.

## When to use

- First step of any Figma-based task.
- When Figma MCP output is truncated, slow or missing assets.

## Inputs

- A Figma URL (`figma.com/design/<fileKey>/<name>?node-id=<a-b>`) or, with the desktop server, the
  current selection.
- The purpose (code, spec, tokens, QA), which decides which calls are needed.

## Workflow

1. **Verify the tools.** List the MCP tools exposed in this session. Do not assume a tool exists:
   names and availability differ between the remote and desktop servers and change over time
   (see [references/tool-matrix.md](references/tool-matrix.md)). Note the server type and follow
   the server's own instructions: the remote server currently asks for `create_session(fileKey,
   description)` before any file tool, then the returned `sessionId` on later calls.
2. **Parse the link:** `fileKey` from the path, `nodeId` from `node-id` with `-` replaced by `:`;
   for branch URLs use the branch key as file key. The remote server needs a link; selection
   only works with the desktop server.
3. **Size the request.** For a large frame (for example taller than about 800 px or many
   sections), call `get_metadata` first to get the node map, then `get_design_context` per
   section node. For a small node, call `get_design_context` directly and fall back to
   `get_metadata` plus per-node calls if the response is truncated (this is Figma's documented flow).
4. **Get the visual reference:** always call `get_screenshot` for the node(s) you will use.
5. **Get tokens:** `get_variable_defs` returns the variables and styles used by the selection
   with resolved values. Values not bound to variables appear only as raw values in the design
   context: record them as hardcoded.
6. **Get component mapping** when implementing: `get_code_connect_map` (and the Code Connect
   tools or the official `figma-code-connect` skill to create mappings).
7. **Assets:** when the server returns localhost asset URLs, use them as given during
   development; do not substitute placeholders or new icon libraries; move assets into the
   project pipeline before merge.
8. **Record provenance:** file key, node IDs, call list, timestamp, warnings.
9. **Fallback without MCP:** say explicitly that live Figma data could not be read, ask for
   exported screenshots, a Dev Mode inspection export or a written spec, and mark every value
   derived from images as `[Assumption]` (measured from pixels, not from variables).

## Outputs

A context bundle for the next skill: node map, design context per section, screenshot
references, variables table (name, resolved value, mode), hardcoded values list, Code Connect
mappings, assets list, warnings and provenance. Values that could not be read are listed as unknown.

## Edge cases

- **Warning "components missing Code Connect mappings":** harmless for specs and audits; for
  implementation, offer to create mappings.
- **"Large MCP response" warning:** expected for big frames; prefer section-level calls.
- **Access denied, rate limits or seat restrictions:** call `whoami` once to diagnose (plan, seat,
  organisation), stop retrying, report the exact error, the calls made and what the file owner
  must change; continue only with the fallback.
- **Variables from a library not enabled in the file:** report names and values, flag missing collection context.
- **Nested components with different radii or paddings:** read each layer; the visible value is not always on the root.

## Acceptance criteria

- [ ] Available tools were verified before use.
- [ ] A screenshot was retrieved for every node used.
- [ ] Variables and hardcoded values are separated.
- [ ] Provenance (file key, node IDs, calls) is recorded.
- [ ] No value is reported that was not returned by Figma or explicitly labelled as estimated.

## Sources

- Figma MCP server documentation (tools and prompts, remote and desktop installation): https://developers.figma.com/docs/figma-mcp-server/
- Figma MCP server guide and official skills: https://github.com/figma/mcp-server-guide
