import json
import pathlib

from mcp_tool_audit.audit import audit, audit_tool, report

SAMPLE = pathlib.Path(__file__).parent.parent / "examples" / "sample_bank_tools.json"


def rules(tool):
    return {f.rule for f in audit_tool(tool)}


def test_unbounded_amount_is_high():
    t = {"name": "x", "description": "Read something harmless here.", "annotations": {"readOnlyHint": True},
         "inputSchema": {"type": "object", "additionalProperties": False,
                         "properties": {"amount": {"type": "number"}}}}
    fs = audit_tool(t)
    assert any(f.rule == "unbounded-amount" and f.severity == "high" for f in fs)


def test_bounded_amount_clean():
    t = {"name": "x", "description": "Read something harmless here.", "annotations": {"readOnlyHint": True},
         "inputSchema": {"type": "object", "additionalProperties": False,
                         "properties": {"amount": {"type": "number", "minimum": 0, "maximum": 10}}}}
    assert "unbounded-amount" not in rules(t)


def test_write_without_confirmation():
    t = {"name": "delete_thing", "description": "Delete the thing for good.", "inputSchema": {"type": "object"}}
    r = rules(t)
    assert "write-without-confirmation" in r and "write-without-annotations" in r


def test_read_only_hint_skips_write_rules():
    t = {"name": "send_report", "description": "Show the report to the user only.",
         "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object"}}
    assert "write-without-confirmation" not in rules(t)


def test_confirm_param_counts():
    t = {"name": "pay_bill", "description": "Pay a bill from the account.", "annotations": {"destructiveHint": True},
         "inputSchema": {"type": "object", "properties": {"confirm": {"type": "boolean"}}}}
    assert "write-without-confirmation" not in rules(t)


def test_personal_data_param():
    t = {"name": "x", "description": "Look up a record by id number.",
         "inputSchema": {"type": "object", "properties": {"cpf": {"type": "string", "pattern": "^[0-9]{11}$"}}}}
    assert "personal-data-param" in rules(t)


def test_duplicate_names():
    t = {"name": "a", "description": "Some long enough description.", "inputSchema": {"type": "object"}}
    assert any(f.rule == "duplicate-name" for f in audit([t, t]))


def test_accepts_bare_list():
    assert audit([{"name": "a"}])


def test_sample_manifest_result():
    m = json.loads(SAMPLE.read_text())
    fs = audit(m)
    by_tool = {}
    for f in fs:
        by_tool.setdefault(f.tool, set()).add(f.rule)
    assert "get_balance" not in by_tool
    assert "pay_bill" not in by_tool
    assert {"unbounded-amount", "write-without-confirmation"} <= by_tool["transfer_funds"]
    assert "short-description" in by_tool["close_account"]
    assert "personal-data-param" in by_tool["lookup_customer"]


def test_report_counts():
    m = json.loads(SAMPLE.read_text())
    text = report(m, audit(m))
    assert "Tools: 5" in text and "with findings: 3" in text
