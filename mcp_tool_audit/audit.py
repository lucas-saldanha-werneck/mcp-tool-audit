"""Rule-based audit of an MCP `tools/list` result. Standard library only."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

WRITE_WORDS = re.compile(
    r"\b(transfer|send|pay|payment|delete|remove|cancel|close|create|update|"
    r"approve|submit|block|freeze|refund|withdraw)\b", re.I)
MONEY_PARAMS = re.compile(r"(amount|value|total|sum|limit)", re.I)
PERSONAL_PARAMS = re.compile(r"(cpf|ssn|iban|account_?number|card_?number|password|pin)", re.I)


@dataclass
class Finding:
    tool: str
    rule: str
    severity: str  # "high" | "medium" | "low"
    message: str


def _is_write(tool: dict) -> bool:
    ann = tool.get("annotations") or {}
    if ann.get("readOnlyHint") is True:
        return False
    text = f"{tool.get('name', '')} {tool.get('description', '')}"
    return bool(WRITE_WORDS.search(text.replace("_", " ")))


def audit_tool(tool: dict) -> list[Finding]:
    name = tool.get("name") or "<unnamed>"
    out: list[Finding] = []
    desc = (tool.get("description") or "").strip()
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    ann = tool.get("annotations") or {}

    if len(desc) < 20:
        out.append(Finding(name, "short-description", "low",
                           "Description is missing or under 20 characters; the model has little to choose with."))
    if not schema or schema.get("type") != "object":
        out.append(Finding(name, "no-input-schema", "medium", "inputSchema is missing or not an object."))
    if props and schema.get("additionalProperties") is not False:
        out.append(Finding(name, "open-schema", "low",
                           "additionalProperties is not false; extra fields pass validation."))

    write = _is_write(tool)
    if write and "readOnlyHint" not in ann and "destructiveHint" not in ann:
        out.append(Finding(name, "write-without-annotations", "medium",
                           "Looks like a write action but has no readOnlyHint/destructiveHint annotation."))
    if write and not re.search(r"confirm|approval|human|review|dry.?run", desc, re.I) \
            and not any(re.search(r"confirm|dry", p, re.I) for p in props):
        out.append(Finding(name, "write-without-confirmation", "high",
                           "Write action with no confirmation or dry-run step in the description or parameters."))

    for pname, p in props.items():
        ptype = (p or {}).get("type")
        if MONEY_PARAMS.search(pname):
            if ptype in ("number", "integer"):
                if "maximum" not in p and "exclusiveMaximum" not in p:
                    out.append(Finding(name, "unbounded-amount", "high",
                                       f"Parameter '{pname}' has no maximum."))
                if "minimum" not in p and "exclusiveMinimum" not in p:
                    out.append(Finding(name, "unbounded-amount", "medium",
                                       f"Parameter '{pname}' has no minimum (negative amounts allowed)."))
            elif ptype == "string":
                out.append(Finding(name, "amount-as-string", "medium",
                                   f"Parameter '{pname}' is a free string; use a number with limits."))
        if PERSONAL_PARAMS.search(pname):
            out.append(Finding(name, "personal-data-param", "medium",
                               f"Parameter '{pname}' looks like personal or secret data passed through the model."))
        if ptype == "string" and not any(k in p for k in ("maxLength", "enum", "pattern", "format")) \
                and not MONEY_PARAMS.search(pname):
            out.append(Finding(name, "unbounded-string", "low",
                               f"String parameter '{pname}' has no maxLength, enum, pattern or format."))
    return out


def audit(manifest: dict | list) -> list[Finding]:
    tools = manifest.get("tools", []) if isinstance(manifest, dict) else manifest
    findings: list[Finding] = []
    names: dict[str, int] = {}
    for t in tools:
        names[t.get("name", "")] = names.get(t.get("name", ""), 0) + 1
        findings.extend(audit_tool(t))
    for n, c in names.items():
        if c > 1:
            findings.append(Finding(n, "duplicate-name", "high", f"Tool name appears {c} times."))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.tool, f.rule))


def report(manifest: dict | list, findings: list[Finding]) -> str:
    tools = manifest.get("tools", []) if isinstance(manifest, dict) else manifest
    flagged = {f.tool for f in findings}
    high = sum(1 for f in findings if f.severity == "high")
    lines = ["# MCP tool audit", "",
             f"Tools: {len(tools)} | with findings: {len(flagged)} | findings: {len(findings)} | high: {high}", ""]
    if not findings:
        lines.append("No findings.")
    for f in findings:
        lines.append(f"- **{f.severity.upper()}** `{f.tool}` ({f.rule}): {f.message}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: python -m mcp_tool_audit.audit <tools.json> [--json]\nExit code 1 if any high finding.")
        return 0
    with open(argv[0], encoding="utf-8") as fh:
        manifest = json.load(fh)
    findings = audit(manifest)
    if "--json" in argv:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        print(report(manifest, findings), end="")
    return 1 if any(f.severity == "high" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
