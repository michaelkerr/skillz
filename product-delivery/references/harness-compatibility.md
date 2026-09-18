# Harness Compatibility

The product-delivery skill assumes only that an agent can:

1. Read Markdown and JSON files.
2. Write files or ask a human to do so.
3. Run a local command, or manually follow the transition table if command execution is unavailable.
4. Present an approval request.

Everything else is a capability enhancement. The skill branches on capabilities, not product names.

## Capability Matrix

| Capability | Required | Used For |
|---|---|---|
| `file_read` | yes | Reading state, events, artifacts, references |
| `file_write` | yes | Writing state, events, artifacts |
| `shell` | no | Running the workflow CLI and test suites |
| `web_research` | no | Discovery research, technology evaluation |
| `code_generation` | no | Implementing work items |
| `conversation` | yes | Discovery, framing, review conversations |
| `approval` | yes | User confirmation at gate transitions |
| `parallel_workers` | no | Delegating independent work items |
| `browser` | no | Testing web applications |
| `mcp` | no | External tool access |

## Harness Notes

### Claude Code

- Discovers skills from `.claude/skills/`. Use a symlink or generated copy from the canonical `.agents/skills/` location.
- Has shell, filesystem, web research, browser, MCP, and parallel worker support.
- Approval via conversation or the AskUserQuestion tool (referenced semantically in SKILL.md as "obtain explicit user approval").

### Cursor

- Discovers skills from `.agents/skills/` natively.
- Has filesystem, shell, and code generation support.
- May have limited web research depending on configuration.

### ChatGPT / Codex

- Discovers skills from the same open format.
- Plugin packaging may be needed for distribution.
- Web and mobile availability depends on plugin setup.

### Hermes

- Scans `.agents/skills/` after project trust is established.
- Supports secure setup, staged approval, and agent-authored skill updates.
- Project trust and scan-time quarantine are additional safety controls.

### Generic / Unknown Harness

- Attach SKILL.md and referenced files manually.
- If shell is unavailable, follow `references/lifecycle.md` for manual transition tracking.
- State management is advisory (agent follows the transition table but cannot enforce it deterministically).

## Degraded Operation

| Missing Capability | Impact | Fallback |
|---|---|---|
| `shell` | Cannot run workflow CLI | Follow lifecycle.md manually; state management is advisory |
| `web_research` | Cannot research unknowns | User provides information directly |
| `parallel_workers` | Cannot delegate work items | Process items sequentially |
| `browser` | Cannot test web apps in browser | User tests manually and reports results |
| `mcp` | No external tool integration | Use available native tools |

## Capability Detection

At initialization, the skill can generate a `.workflow/config.json` with detected capabilities. The SKILL.md procedure branches on these capabilities using semantic checks:

- "If shell execution is available, use the CLI for state management."
- "If shell is unavailable, follow the transition table manually."
- "Delegate only if the current harness supports isolated workers."

No vendor-specific tool names appear in SKILL.md.
