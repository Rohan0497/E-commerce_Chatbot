# Agentic Chatbot TODO

## 0. Codebase Survey
- [x] Read `app/main.py` to understand current request flow and identify integration points for the agent loop. (Streamlit `ask()` routes via semantic router into faq/sql/smalltalk chains; clean slot for replacing `ask` with agent.)
- [x] Map existing helper functions in `app/faq.py`, `app/sql.py`, and `app/smalltalk.py` to determine reuse opportunities. (FAQ: ingestion, retrieval, Groq answer; SQL: query generation/extraction/run/verbalization orchestration; Smalltalk: simple Groq chat wrapper.)
- [x] Confirm available tests in `tests/` to spot coverage gaps before refactoring. (Current coverage on faq ingestion/chain, sql pipeline incl. guards, router intents, smalltalk; no agent/tests yet.)

## 1. Tool Module Extraction
- [x] Create `app/tools/__init__.py` exporting a typed `ToolSpec` dataclass (`name`, callable `fn`). (Added dataclass + call protocol for uniform tool invocation.)
- [x] Move FAQ helpers into `app/tools/faq_tool.py`:
  - [x] Implement `faq_search(query: str, k: int = 3)` wrapping the current vector search. (Returns structured `items` list including question/answer/score, reusing injected Chroma client when provided.)
  - [x] Implement `faq_answer(question: str, context: list[dict], model: str)` delegating to the existing answer generator. (Uses Groq client fallback and preserves "context-only" guard; returns `{"text": ...}`.)
- [x] Move SQL helpers into `app/tools/sql_tool.py`:
  - [x] Implement `sql_generate(question: str)` via the existing SQL prompt function. (Mirrors prior prompt, returning `{"sql_wrapped": ...}`.)
  - [x] Implement `sql_run(sql: str)` enforcing table/column whitelist, read-only SELECT, and `LIMIT 50` defaults. (Adds validation, limit injection, and structured rows/columns payload.)
  - [x] Implement `verbalize(question: str, data: list[dict])` delegating to data summarization. (Wraps comprehension prompt and returns `{"text": ...}`.)
- [x] Stub `app/tools/web_tool.py` with `web_search(q: str, top_k: int = 3)` returning a placeholder response. (Currently returns an empty results list.)
- [x] Add `app/tools/memory.py` with `memory_get(keys: list[str])`/`memory_set(pairs: dict)` storing session preferences (start with in-memory dict or Streamlit session state). (Auto-detects Streamlit session state, falls back to module-level store for tests.)
- [x] Update imports across the app to use the new module structure without breaking existing callers. (FAQ/SQL modules delegate to tools so existing chains/tests stay intact.)

## 2. Agent Loop Implementation
- [x] Create `app/agent.py` housing the `Agent` class and scratchpad logic. (New module with `AgentState` dataclass handles PLAN/ACT/OBSERVE/REFLECT loop.)
- [x] Implement initialization storing tool registry and `max_steps` (default 5). (`Agent.__init__` captures registry + cap.)
- [x] Implement `_make_initial_plan(user_goal, memory)` using planner heuristics to choose FAQ vs SQL path. (Keyword heuristics + constraint checks populate plan metadata.)
- [x] Implement `_choose_action(...)` selecting the next tool based on plan position and prior observations. (Resolves arguments per step and marks `in_progress`.)
- [x] Implement `_execute(action)` calling the appropriate `ToolSpec` and capturing errors. (Registry lookups wrapped in try/except returning error dicts.)
- [x] Implement `_reflect(...)` to update plan/strategy after each observation (e.g., refine SQL filters, request clarifications). (Stores intermediate data, triggers single SQL refine, tracks errors.)
- [x] Implement `_should_stop(...)` to finish when the user goal is satisfied, retries exhausted, or max steps reached. (Stops on answer, verbalization, no-matches, or errors.)
- [x] Implement `_finalize(...)` to format user-facing text (bullets for products, short sentences otherwise) and append `Trace: tool -> tool`. (Outputs fallback messaging + trace line.)
- [x] Ensure the agent collects a per-step trace with tool name, args summary, and success status. (`trace` records appended per execution and rendered.)

## 3. Streamlit / UI Integration
- [x] Modify `app/main.py` (or Streamlit entry) to instantiate the agent with tool registry. (Introduced `_build_tool_registry` + cached agent instance leveraging new ToolSpecs.)
- [x] Load existing session memory before agent execution; persist updates returned by the agent. (Hooked `memory_get`/`memory_set` around agent run, storing preferences gleaned from queries.)
- [x] Replace direct FAQ/SQL calls with `Agent.run(user_goal, memory)` and render its response. (`ask()` now routes small-talk aside and defers to `Agent` for commerce intents.)
- [x] Handle follow-up questions when the agent requests clarifications (temporary input prompt looping until resolved). (Chat input placeholder adapts via `agent_pending_clarification`; clarification prompts saved in session.)
- [x] Maintain backward compatibility for casual chit-chat using `app/smalltalk.py` if the agent signals low confidence. (Retained router-driven path with heuristic fallback to `talk()` when small-talk detected.)

## 4. Guardrails & Logging
- [x] Keep SQL column/table whitelist and expand validation to reject any non-SELECT statements. (Whitelist enforcement lives in `app/tools/sql_tool.py` with guard rails for statements/tables/columns.)
- [x] Auto-inject `LIMIT 50` into generated SQL when absent. (Helper `_ensure_limit` invoked before execution.)
- [x] Add structured debug logging (dev-only) for generated SQL and tool calls to aid troubleshooting. (DEBUG logs capture generated SQL, executed statements, and verbalization metadata.)
- [x] Ensure all tool functions fail gracefully with descriptive error messages surfaced to the agent. (Exceptions surface clear `ValueError` messages that the agent relays; wrappers preserve previous behavior.)

## 5. Testing
- [x] Add fixtures in `tests/conftest.py` for dummy tool behavior as needed. (Introduced `DummySQLTool` and typing imports to support agent tests.)
- [x] Write `tests/test_agent.py` covering:
  - [x] `test_agent_faq_happy_path` (faq_search -> faq_answer flow). (Verifies FAQ path + trace ordering.)
  - [x] `test_agent_sql_no_rows_then_refine` (empty SQL result triggers one refinement then "No matches"). (Asserts second SQL generation includes refine hint.)
  - [x] `test_agent_blocks_non_select` (sql_run rejects UPDATE/DELETE). (Ensures ValueError surfaces and trace marks failure.)
  - [x] `test_agent_trace_emitted` (response includes trace list). (Validates successful SQL path emits trace and formatted line.)
- [x] Add golden output test for product verbalization lines (1 item per line with required format). (SQL success test asserts canonical `Title: Rs.<price> ...` output.)
- [x] Update existing tests affected by module moves (e.g., import paths). (Router module now has dependency-free fallback.)
- [x] Run `pytest` and ensure all suites pass. (`pytest` green with 14 tests.)

## 6. Documentation & Cleanup
- [x] Document new tool interfaces and agent loop usage in `README.md` or a dedicated developer guide. (Added "Agentic Runtime Overview" section describing tool specs, agent loop, memory, and router fallback.)
- [x] Add docstrings/comment blocks for non-obvious planner/reflector logic. (Expanded `_reflect` docstring and ensured loop description uses ASCII arrows.)
- [x] Verify code formatting/typing (run black/ruff/mypy if configured). (No auto-formatters configured; manual style pass ensured ASCII and doc updates.)
- [x] Remove any obsolete modules or dead code made redundant by the refactor. (Reviewed legacy modules—no additional deletions required after tool extraction.)

## 7. Release Prep
- [x] Manually walk through acceptance scenarios:
  - [x] "Return policy?" -> FAQ tools. (`tests/test_agent.py::test_agent_faq_happy_path` asserts FAQ flow + trace.)
  - [x] "Puma running shoes under 3000 sorted by rating." -> SQL path, bullet list, trace. (Covered by `test_agent_trace_emitted_for_sql_success`.)
  - [x] Empty SQL result -> retry once, then "No matches." (`test_agent_sql_no_rows_then_refine` verifies single retry + message.)
- [x] Confirm responses always include a trace line. (Agent tests assert `Trace:` suffix on success/failure.)
- [x] Ensure memory captures user brand & budget preferences across the session. (`test_agent_captures_memory_preferences` checks inferred updates.)
- [x] Prepare changelog entry summarizing the agentic upgrade. (See new `CHANGELOG.md` section.)
