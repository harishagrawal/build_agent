"""Exercises the full pipeline (prompt -> write script -> execute -> validate)
without calling the real Claude API: `claude_client.generate_code` is
monkeypatched to hand back canned Python source instead.

The first canned response is deliberately buggy (wrong field name) so this
also proves the self-healing retry loop actually re-prompts and recovers.
"""

import json
import textwrap

import pytest

import config
from agent import claude_client, orchestrator

BUGGY_SOLUTION = textwrap.dedent('''\
    import argparse, csv, json

    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)
        args = p.parse_args()

        with open(args.input) as f:
            orders = json.load(f)

        totals = {}
        for o in orders:
            # BUG: wrong key name, raises KeyError on real input
            name = o["customer_name"]
            totals[name] = totals.get(name, 0) + o["quantity"] * o["unit_price"]

        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["customer", "total_spend", "order_count"])

    if __name__ == "__main__":
        main()
    ''')

FIXED_SOLUTION = textwrap.dedent('''\
    import argparse, csv, json

    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)
        args = p.parse_args()

        with open(args.input) as f:
            orders = json.load(f)

        totals, counts = {}, {}
        for o in orders:
            name = o["customer"]
            totals[name] = totals.get(name, 0.0) + o["quantity"] * o["unit_price"]
            counts[name] = counts.get(name, 0) + 1

        rows = sorted(
            ((name, round(total, 2), counts[name]) for name, total in totals.items()),
            key=lambda r: r[1],
            reverse=True,
        )

        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["customer", "total_spend", "order_count"])
            w.writerows(rows)

    if __name__ == "__main__":
        main()
    ''')


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Point every config path at a scratch directory for this test."""
    requirements = tmp_path / "requirements.md"
    requirements.write_text("Summarize spend per customer.", encoding="utf-8")

    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps([
        {"customer": "Alice", "item": "Widget", "quantity": 3, "unit_price": 9.99},
        {"customer": "Bob", "item": "Gadget", "quantity": 1, "unit_price": 49.5},
        {"customer": "Alice", "item": "Gizmo", "quantity": 2, "unit_price": 14.0},
    ]), encoding="utf-8")

    output_path = tmp_path / "result.csv"
    script_path = tmp_path / "solution.py"

    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")

    return requirements, input_path, output_path, script_path


def test_self_healing_retry_recovers_from_buggy_first_attempt(tmp_project, monkeypatch):
    requirements, input_path, output_path, script_path = tmp_project

    responses = iter([BUGGY_SOLUTION, FIXED_SOLUTION])
    monkeypatch.setattr(claude_client, "generate_code", lambda *a, **k: next(responses))
    monkeypatch.setattr(claude_client, "get_client", lambda: object())

    result = orchestrator.run(
        requirements_path=requirements,
        input_path=input_path,
        output_path=output_path,
        generated_script_path=script_path,
        max_attempts=3,
    )

    assert result.success, result.summary
    assert result.attempts == 2  # failed once, fixed on retry
    assert script_path.read_text() == FIXED_SOLUTION

    rows = output_path.read_text().strip().splitlines()
    assert rows[0] == "customer,total_spend,order_count"
    assert rows[1] == "Alice,57.97,2"  # 3*9.99 + 2*14.0 = 29.97 + 28.00
    assert rows[2] == "Bob,49.5,1"


def test_gives_up_after_max_attempts_when_every_attempt_fails(tmp_project, monkeypatch):
    requirements, input_path, output_path, script_path = tmp_project

    monkeypatch.setattr(claude_client, "generate_code", lambda *a, **k: BUGGY_SOLUTION)
    monkeypatch.setattr(claude_client, "get_client", lambda: object())

    result = orchestrator.run(
        requirements_path=requirements,
        input_path=input_path,
        output_path=output_path,
        generated_script_path=script_path,
        max_attempts=2,
    )

    assert not result.success
    assert result.attempts == 2
    assert "KeyError" in result.summary or "customer_name" in result.summary
