"""Agent loop orchestrating plan/act/observe/reflect behavior."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.tools import ToolSpec

FAQ_KEYWORDS = {
    "return",
    "refund",
    "shipping",
    "payment",
    "warranty",
    "delivery",
    "exchange",
}

SQL_KEYWORDS = {
    "price",
    "cost",
    "cheap",
    "discount",
    "rating",
    "brand",
    "size",
    "availability",
    "stock",
    "show",
    "list",
    "buy",
    "product",
    "shoe",
    "shoes",
    "laptop",
    "phones",
}

BRAND_HINTS = {"nike", "puma", "adidas", "reebok", "apple", "samsung"}


@dataclass(slots=True)
class AgentState:
    """Mutable state tracked while the agent loop executes."""

    plan: Dict[str, Any]
    last_result: Optional[Dict[str, Any]] = None
    step_index: Optional[int] = None


class Agent:
    """Simple reflexive agent that follows PLAN -> ACT -> OBSERVE -> REFLECT loop."""

    def __init__(self, tools: Dict[str, ToolSpec], max_steps: int = 5) -> None:
        self.tools = tools
        self.max_steps = max_steps

    # --------------------------------------------------------------------- run
    def run(self, user_goal: str, memory: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the agent loop for a given user goal."""
        memory = memory or {}
        plan = self._make_initial_plan(user_goal, memory)
        trace: List[Dict[str, Any]] = []
        tool_order: List[str] = []

        if plan.get("needs_clarification"):
            message = self._format_clarification(plan["needs_clarification"])
            final = self._finalize(
                user_goal=user_goal,
                plan=plan,
                last_result=None,
                tool_order=[],
                trace_records=trace,
                override_text=message,
            )
            return final

        state = AgentState(plan=plan)
        for _ in range(self.max_steps):
            action = self._choose_action(user_goal, memory, state)
            if action is None:
                break

            try:
                result = self._execute(action)
            except Exception as exc:  # pragma: no cover - defensive
                result = {"error": str(exc)}

            trace.append(
                {
                    "tool": action["tool"],
                    "args": action.get("args", {}),
                    "ok": "error" not in result,
                }
            )
            tool_order.append(action["tool"])
            state.last_result = result

            self._reflect(action, state)

            if self._should_stop(state):
                break

        final = self._finalize(
            user_goal=user_goal,
            plan=state.plan,
            last_result=state.last_result,
            tool_order=tool_order,
            trace_records=trace,
        )
        return final

    # -------------------------------------------------------------- plan stage
    def _make_initial_plan(self, user_goal: str, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Build the initial multi-step plan and identify missing info."""
        lowered = user_goal.lower()
        plan_type = "faq"
        if self._mentions(lowered, FAQ_KEYWORDS):
            plan_type = "faq"
        elif self._mentions(lowered, SQL_KEYWORDS):
            plan_type = "sql"

        plan: Dict[str, Any] = {
            "type": plan_type,
            "steps": [],
            "needs_clarification": [],
            "data": {},
            "retries": 0,
        }

        if plan_type == "faq":
            plan["steps"] = [
                {"tool": "faq_search", "status": "pending"},
                {"tool": "faq_answer", "status": "pending"},
            ]
        else:
            plan["steps"] = [
                {"tool": "sql_generate", "status": "pending"},
                {"tool": "sql_run", "status": "pending"},
                {"tool": "verbalize", "status": "pending"},
            ]
            plan["needs_clarification"] = self._missing_constraints(lowered, memory)

        preference_updates = self._guess_preferences(lowered, memory)
        if preference_updates:
            plan["data"]["memory_updates"] = preference_updates

        return plan

    # --------------------------------------------------------------- act stage
    def _choose_action(
        self,
        user_goal: str,
        memory: Dict[str, Any],
        state: AgentState,
    ) -> Optional[Dict[str, Any]]:
        """Select the next tool call based on plan progress."""
        plan = state.plan
        for idx, step in enumerate(plan["steps"]):
            if step["status"] != "pending":
                continue

            tool_name = step["tool"]
            args: Dict[str, Any] = {}

            if tool_name == "faq_search":
                args = {"query": user_goal, "k": 3}
            elif tool_name == "faq_answer":
                context = plan["data"].get("faq_items", [])
                args = {"question": user_goal, "context": context}
            elif tool_name == "sql_generate":
                question = self._apply_memory_to_question(user_goal, memory)
                if plan["data"].get("refine_hint"):
                    question += " (If no products match, relax filters slightly and broaden the search.)"
                args = {"question": question}
            elif tool_name == "sql_run":
                sql_query = plan["data"].get("sql_query")
                if not sql_query:
                    return None
                args = {"sql": sql_query}
            elif tool_name == "verbalize":
                rows = plan["data"].get("rows", [])
                args = {"question": user_goal, "data": rows}
            else:
                continue

            step["status"] = "in_progress"
            state.step_index = idx
            return {"tool": tool_name, "args": args, "index": idx}

        return None

    # ------------------------------------------------------------ execute tool
    def _execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool from the registry and return its result."""
        tool_name = action["tool"]
        spec = self.tools.get(tool_name)
        if spec is None:
            return {"error": f"Tool '{tool_name}' is not registered."}

        args = dict(action.get("args", {}))
        try:
            return spec.fn(args)
        except Exception as exc:
            return {"error": str(exc)}

    # -------------------------------------------------------------- reflect
    def _reflect(self, action: Dict[str, Any], state: AgentState) -> None:
        """
        Update plan progress and react to observations.

        Records artifacts (FAQ context, SQL rows, verbalized text) and when SQL
        returns no results it performs at most one automatic refinement by
        resetting the SQL-related steps. Errors propagate via `plan["data"]["error"]`.
        """
        plan = state.plan
        idx = action.get("index")
        if idx is not None and 0 <= idx < len(plan["steps"]):
            plan["steps"][idx]["status"] = "completed"

        result = state.last_result or {}
        tool_name = action["tool"]

        if "error" in result:
            plan["data"]["error"] = result["error"]
            return

        if tool_name == "faq_search":
            plan["data"]["faq_items"] = result.get("items", [])
        elif tool_name == "faq_answer":
            plan["data"]["answer"] = result.get("text", "")
        elif tool_name == "sql_generate":
            wrapped = result.get("sql_wrapped", "")
            extracted = self._extract_sql(wrapped)
            plan["data"]["sql_wrapped"] = wrapped
            plan["data"]["sql_query"] = extracted
            if not extracted:
                plan["data"]["error"] = "The model did not return a valid SQL query."
        elif tool_name == "sql_run":
            rows = result.get("rows", [])
            plan["data"]["rows"] = rows
            plan["data"]["columns"] = result.get("columns", [])

            if isinstance(rows, list) and not rows:
                if plan["retries"] < 1:
                    plan["retries"] += 1
                    plan["data"]["refine_hint"] = True
                    self._reset_sql_steps(plan)
                else:
                    plan["data"]["no_matches"] = True
        elif tool_name == "verbalize":
            plan["data"]["verbalization"] = result.get("text", "")

    # -------------------------------------------------------------- stop check
    def _should_stop(self, state: AgentState) -> bool:
        """Check whether the goal is satisfied or the plan is exhausted."""
        plan = state.plan
        data = plan["data"]

        if data.get("error"):
            return True

        if plan["type"] == "faq":
            return bool(data.get("answer"))

        if plan["type"] == "sql":
            if data.get("verbalization"):
                return True
            if data.get("no_matches"):
                return True

        return False

    # -------------------------------------------------------------- finalize
    def _finalize(
        self,
        user_goal: str,
        plan: Dict[str, Any],
        last_result: Optional[Dict[str, Any]],
        tool_order: List[str],
        trace_records: List[Dict[str, Any]],
        override_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compose the final user-facing response and trace."""
        data = plan.get("data", {})
        text = override_text or ""

        if not text and data.get("error"):
            text = f"Sorry, something went wrong: {data['error']}"
        elif not text and plan["type"] == "faq":
            if data.get("answer"):
                text = data["answer"]
            else:
                text = "I don't have an answer right now."
        elif not text and plan["type"] == "sql":
            if data.get("verbalization"):
                text = data["verbalization"]
            elif data.get("no_matches"):
                text = "No matches."
            else:
                text = "I'm still working on it, but I couldn't find matching products."

        if not text:
            text = "I don't have an answer right now."

        trace_line = self._format_trace(tool_order)
        final_text = f"{text}\n{trace_line}"

        return {
            "text": final_text,
            "trace": trace_records,
            "plan": plan,
            "goal": user_goal,
            "memory_updates": data.get("memory_updates", {}),
        }

    # -------------------------------------------------------------- utilities
    def _missing_constraints(self, lowered_goal: str, memory: Dict[str, Any]) -> List[str]:
        """Determine which product constraints are absent from the goal+memory."""
        needs: List[str] = []
        brand_known = any(hint in lowered_goal for hint in BRAND_HINTS) or memory.get("brand")
        price_known = bool(re.search(r"\b\d{3,5}\b", lowered_goal)) or memory.get("price_ceiling")

        if not brand_known:
            needs.append("preferred brand")
        if not price_known:
            needs.append("budget ceiling")

        return needs

    def _apply_memory_to_question(self, user_goal: str, memory: Dict[str, Any]) -> str:
        """Inject stored preferences into the SQL question when available."""
        pieces = [user_goal]
        if memory.get("brand") and memory["brand"].lower() not in user_goal.lower():
            pieces.append(f"(Prefer brand {memory['brand']})")
        if memory.get("price_ceiling") and str(memory["price_ceiling"]) not in user_goal:
            pieces.append(f"(Keep price under {memory['price_ceiling']})")
        return " ".join(pieces)

    def _reset_sql_steps(self, plan: Dict[str, Any]) -> None:
        """Reset SQL-related steps to pending for a refinement attempt."""
        for step in plan["steps"]:
            if step["tool"] in {"sql_generate", "sql_run", "verbalize"}:
                step["status"] = "pending"
        plan["data"].pop("sql_query", None)
        plan["data"].pop("rows", None)
        plan["data"].pop("verbalization", None)

    def _format_clarification(self, needs: List[str]) -> str:
        """Generate a clarification question for missing constraints."""
        joined = " and ".join(needs) if len(needs) <= 2 else ", ".join(needs[:-1]) + f", and {needs[-1]}"
        return f"Could you share the {joined} you're looking for?"

    def _format_trace(self, tool_order: List[str]) -> str:
        """Render the trace line required by the runtime."""
        if not tool_order:
            return "Trace: none"
        path = " -> ".join(tool_order)
        return f"Trace: {path}"

    @staticmethod
    def _extract_sql(payload: str) -> Optional[str]:
        """Extract SQL text from <SQL>...</SQL> wrapper."""
        matches = re.findall(r"<SQL>(.*?)</SQL>", payload, flags=re.IGNORECASE | re.DOTALL)
        if not matches:
            return None
        return matches[0].strip()

    @staticmethod
    def _mentions(text: str, keywords: set[str]) -> bool:
        """Check if any keyword appears in text."""
        return any(word in text for word in keywords)

    def _guess_preferences(self, text: str, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract simple preference hints from the user goal."""
        updates: Dict[str, Any] = {}
        if not memory.get("brand"):
            for brand in BRAND_HINTS:
                if brand in text:
                    updates["brand"] = brand.title()
                    break

        if not memory.get("price_ceiling"):
            price_match = re.search(r"(?:under|below|less than)\s*(\d{3,6})", text)
            if price_match:
                updates["price_ceiling"] = int(price_match.group(1))
            else:
                numbers = re.findall(r"\b\d{3,6}\b", text)
                if numbers:
                    try:
                        updates["price_ceiling"] = int(numbers[0])
                    except ValueError:
                        pass

        return updates
