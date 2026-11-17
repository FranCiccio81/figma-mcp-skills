<!-- evaluation: executed -->
# Evaluation results

## 2026-11-17, live run against the remote Figma MCP server

Scenario: read the Buttons frame used by `ds/specs/active/button-spec.md`
(file key from that spec, node `729-17557`) to produce design context.

| Step | Expected by the skill | Observed |
|---|---|---|
| Verify tools | List tools before use | Remote server tools listed; server instructions require `create_session` (not documented before, skill updated to 1.1.0) |
| Parse link | `729-17557` becomes `729:17557` | Done |
| `get_metadata`, `get_variable_defs` | Read node | Both refused: "you don't have edit access to this file" |
| Diagnose | `whoami` once | Account has Full seats on a Starter team plan and on the Swissquote Enterprise organisation; the file is not shared with edit rights to this account |
| `create_session` | Retry once with the documented prerequisite | Refused with the same access error |
| Fallback | Stop retrying, report, no invented values | Stopped after one diagnosis; no value was produced from this file |

Result: the access-failure path (eval case 2 pattern) behaves as specified. The happy path
(eval case 1) remains to be run on a file shared with this account.
