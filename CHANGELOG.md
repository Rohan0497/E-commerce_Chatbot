# Changelog

## [Unreleased]
- Introduced agentic runtime:
  - Extracted tool layer (`app/tools/`) with FAQ, SQL, web, and memory helpers unified via `ToolSpec`.
  - Added `Agent` loop for plan/act/observe/reflect behavior with trace emission and SQL refinement guard.
  - Integrated agent with Streamlit entrypoint, session memory, and small-talk routing.
- Strengthened SQL guardrails (table/column whitelist, LIMIT enforcement, debug logging).
- Expanded test suite with agent behavior coverage and router fallback for environments without `semantic_router`.
- Documented agent architecture in README and added acceptance tests for brand/budget memory capture.
