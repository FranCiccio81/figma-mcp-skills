# figma-mcp-skills

Real-world learnings from using the **Figma MCP Server** inside **Claude Code** to automate UX documentation and design-to-code workflows.

## What's in here

```
figma-mcp-skills/
├── docs/
│   └── workflow-figma-mcp.md     # Step-by-step MCP workflow guide
└── components/
    └── input-documentation.md    # Full handoff doc — Input component
```

## The workflow (TL;DR)

```
get_metadata → get_design_context (per section) → get_screenshot → get_variable_defs
```

Then ask Claude to generate a complete Markdown handoff document covering:
anatomy, states, tokens, accessibility, and open questions.

## Design System

**Foundations — Laboratoire Innotech International**
Figma file key: `YMXQcB0QWivNJGwH3jJUI7`

## Requirements

- [Claude Code](https://claude.ai/claude-code) CLI
- Figma Desktop app with MCP server enabled
- A Figma file open with a frame selected

## License

MIT
