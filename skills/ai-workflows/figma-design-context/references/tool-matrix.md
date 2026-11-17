# Figma MCP tool matrix

Observed on 2026-11-17. Always confirm with the tool list of the current session; Figma adds and
renames tools regularly.

| Tool | Remote server | Desktop server | Purpose |
|---|---|---|---|
| `get_design_context` | yes | yes | Structured representation of a node, React + Tailwind by default |
| `get_metadata` | yes | yes | Sparse XML map: layer IDs, names, types, positions, sizes |
| `get_screenshot` | yes | yes | Image of the node |
| `get_variable_defs` | yes | yes | Variables and styles used by the node, with values |
| `get_code_connect_map` | yes | yes | Existing Figma component to code mappings |
| `add_code_connect_map` | yes | yes | Adds a mapping |
| `get_figjam` | yes | yes | FigJam content |
| `create_design_system_rules` | varies | yes | Generates a rules file for the agent |
| `search_design_system`, `get_libraries` | yes | no | Library and component search |
| `use_figma`, `create_new_file`, `upload_assets`, `generate_diagram` | yes | no | Write to the canvas (load the official `figma-use` skill first) |
| `whoami` | yes | no | Identity, plan and seat; first call when access fails |
| `create_session` | yes | no | Required by the remote server before file tools (observed 2026-11-17) |

Endpoints:

- Remote (recommended by Figma): `https://mcp.figma.com/mcp`, OAuth.
- Desktop: `http://127.0.0.1:3845/mcp` (HTTP transport; the older `/sse` endpoint is deprecated),
  enabled from Figma Desktop in Dev Mode.

Claude Code:

```bash
claude mcp add --transport http figma https://mcp.figma.com/mcp           # remote
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp   # desktop
```

Lessons from the 2026-03-28 field test (Foundations file, Input frame 1697 × 4407 px, 4 sections):
section-level calls completed a full handoff in about 2 min 17 s; the "Large MCP response" warning
was expected; eight hardcoded values were found; the visible border radius came from a nested layer.
