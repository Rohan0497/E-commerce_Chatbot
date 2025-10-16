from typing import Any, Callable, Dict, List

import pytest

from app.agent import Agent
from app.tools import ToolSpec


def make_agent(overrides: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] | None = None) -> Agent:
    """Build an Agent with overridable tool implementations."""
    overrides = overrides or {}

    def noop(_args: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    default_tools = {
        "faq_search": lambda args: {"items": []},
        "faq_answer": lambda args: {"text": ""},
        "sql_generate": lambda args: {"sql_wrapped": "<SQL>SELECT * FROM product;</SQL>"},
        "sql_run": lambda args: {"rows": [], "columns": []},
        "verbalize": lambda args: {"text": ""},
        "web_search": lambda args: {"results": []},
    }

    default_tools.update(overrides)
    specs = {name: ToolSpec(name=name, fn=fn) for name, fn in default_tools.items()}
    return Agent(tools=specs, max_steps=5)


def test_agent_faq_happy_path():
    faq_items = [{"question": "Return policy?", "answer": "30-day returns", "score": 0.9}]

    def faq_search(args: Dict[str, Any]) -> Dict[str, Any]:
        assert args["query"] == "Return policy?"
        return {"items": faq_items}

    def faq_answer(args: Dict[str, Any]) -> Dict[str, Any]:
        assert args["context"][0]["answer"] == "30-day returns"
        return {"text": "You can return items within 30 days."}

    agent = make_agent({"faq_search": faq_search, "faq_answer": faq_answer})
    result = agent.run("Return policy?", memory={})

    assert result["text"].splitlines()[0] == "You can return items within 30 days."
    assert result["text"].endswith("Trace: faq_search -> faq_answer")
    assert [entry["tool"] for entry in result["trace"]] == ["faq_search", "faq_answer"]
    assert all(entry["ok"] for entry in result["trace"])


def test_agent_sql_no_rows_then_refine():
    generate_calls: List[str] = []
    run_calls: List[str] = []

    def sql_generate(args: Dict[str, Any]) -> Dict[str, Any]:
        generate_calls.append(args["question"])
        return {"sql_wrapped": "<SQL>SELECT * FROM product;</SQL>"}

    def sql_run(args: Dict[str, Any]) -> Dict[str, Any]:
        run_calls.append(args["sql"])
        return {"rows": [], "columns": ["title"]}

    agent = make_agent({"sql_generate": sql_generate, "sql_run": sql_run})
    query = "Puma running shoes under 3000 sorted by rating."
    result = agent.run(query, memory={})

    assert result["text"].splitlines()[0] == "No matches."
    assert generate_calls[0] == query
    assert "relax filters" in generate_calls[1]
    assert len(run_calls) == 2
    assert result["text"].endswith("Trace: sql_generate -> sql_run -> sql_generate -> sql_run")


def test_agent_blocks_non_select():
    def sql_run(_args: Dict[str, Any]) -> Dict[str, Any]:
        raise ValueError("Only SELECT statements are allowed.")

    agent = make_agent({"sql_run": sql_run})
    result = agent.run("List Adidas shoes under 4000.", memory={})

    assert "Only SELECT statements are allowed." in result["text"]
    tools = [entry["tool"] for entry in result["trace"]]
    assert tools == ["sql_generate", "sql_run"]
    assert result["trace"][1]["ok"] is False


def test_agent_trace_emitted_for_sql_success():
    rows = [
        {
            "title": "Velocity Runner",
            "price": 2999,
            "discount": 0.5,
            "avg_rating": 4.9,
            "product_link": "http://x/1",
        }
    ]

    def sql_run(_args: Dict[str, Any]) -> Dict[str, Any]:
        return {"rows": rows, "columns": list(rows[0].keys())}

    def verbalize(args: Dict[str, Any]) -> Dict[str, Any]:
        data = args["data"]
        line = (
            f"{data[0]['title']}: Rs.{data[0]['price']} "
            f"({int(data[0]['discount'] * 100)}% off), "
            f"Rating: {data[0]['avg_rating']} {data[0]['product_link']}"
        )
        return {"text": line}

    agent = make_agent({"sql_run": sql_run, "verbalize": verbalize})
    result = agent.run("Puma running shoes under 3000 sorted by rating.", memory={})

    expected_line = "Velocity Runner: Rs.2999 (50% off), Rating: 4.9 http://x/1"
    assert result["text"].splitlines()[0] == expected_line
    assert result["text"].endswith("Trace: sql_generate -> sql_run -> verbalize")
    assert [entry["tool"] for entry in result["trace"]] == ["sql_generate", "sql_run", "verbalize"]
    assert all(entry["ok"] for entry in result["trace"])


def test_agent_captures_memory_preferences():
    rows = [
        {
            "title": "Sprint Master",
            "price": 2899,
            "discount": 0.4,
            "avg_rating": 4.7,
            "product_link": "http://x/2",
        }
    ]

    def sql_run(_args: Dict[str, Any]) -> Dict[str, Any]:
        return {"rows": rows, "columns": list(rows[0].keys())}

    def verbalize(args: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": "Sprint Master: Rs.2899 (40% off), Rating: 4.7 http://x/2"}

    agent = make_agent({"sql_run": sql_run, "verbalize": verbalize})
    result = agent.run("Need Puma shoes under 3000.", memory={})

    updates = result["memory_updates"]
    assert updates["brand"] == "Puma"
    assert updates["price_ceiling"] == 3000
    assert result["text"].splitlines()[0] == "Sprint Master: Rs.2899 (40% off), Rating: 4.7 http://x/2"
    assert result["text"].endswith("Trace: sql_generate -> sql_run -> verbalize")
