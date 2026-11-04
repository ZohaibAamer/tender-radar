# ADR-0001: Governance is enforced in the MCP server, not the agent

Status: accepted

## Context

The project's central claim is that the agent runs on *governed* data: it may
use declared metrics and parameterized search, never free SQL. That rule has
to live somewhere. The obvious place — the agent loop — is the wrong one: an
agent-side rule binds only our own CLI loop. Anyone connecting any other
MCP client — a desktop AI app, MCP Inspector — to the same server would
bypass it entirely.

## Decision

The MCP server simply **offers no tool that accepts SQL**. Aggregates exist
only through `query_metric`, which compiles requests against
`semantic/layer.yaml`; search filters bind as SQL parameters; the warehouse
connection is read-only. The agent loop contains no governance logic at all —
it consumes tools and collects citations.

## Consequences

- Governance holds for every client, however the model is driven, prompted,
  or jailbroken. A prompt injection can at worst call governed tools.
- The semantic layer's refusals (`GovernanceError`) are written for the
  model to read, so a refused query comes back as a correctable message, not
  a dead end.
- The claim is testable without an LLM: `tests/test_mcp_tools.py` asserts no
  tool has a SQL-shaped parameter, and `tests/test_semantic.py` covers what
  the compiler refuses.
- Cost: agents cannot run ad-hoc analytics we didn't declare. Extending the
  surface means editing one YAML file, which is the point.
