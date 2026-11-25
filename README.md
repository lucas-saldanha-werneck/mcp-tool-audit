# mcp-tool-audit

Independent demo, not affiliated with Jobgether (cliente não diz).

A small Python script that reads the JSON list of tools an MCP server exposes (`tools/list`) and flags definitions that are risky when an AI agent can move money. I wrote it after reading a posting for an AI agent engineer in banking, where agents get wired to internal systems over MCP.

It uses only the Python standard library. About 150 lines.

## Run it

```
python -m mcp_tool_audit examples/sample_bank_tools.json
python -m mcp_tool_audit tools.json --json
```

The exit code is 1 when there is at least one high finding, so it can gate a CI job.

## What it checks

| Rule | Severity | Meaning |
|---|---|---|
| `write-without-confirmation` | high | Write-like tool with no confirm or dry-run step in the description or parameters |
| `unbounded-amount` | high / medium | Money parameter with no maximum (high) or no minimum (medium) |
| `duplicate-name` | high | Two tools share a name |
| `write-without-annotations` | medium | Write-like tool without `readOnlyHint` or `destructiveHint` |
| `personal-data-param` | medium | Parameter named like a CPF, IBAN, card number, password or PIN |
| `amount-as-string` | medium | Money parameter typed as a free string |
| `no-input-schema` | medium | Missing or non-object `inputSchema` |
| `open-schema`, `unbounded-string`, `short-description` | low | Loose schema or thin description |

"Write-like" is a keyword guess on the name and description (transfer, pay, delete, close and so on). A `readOnlyHint: true` annotation turns it off.

## Example result

`examples/sample_bank_tools.json` holds five tools I invented. It is example data, not taken from any real bank or product. The run reports 13 findings on 3 of the 5 tools, 3 of them high: `transfer_funds` has no amount limit and no confirmation step, and `close_account` has no confirmation step. `get_balance` and `pay_bill` come out clean.

## What was tested

- 10 offline pytest tests, run locally and in GitHub Actions on every push.
- Each rule on a small hand-written tool.
- The bundled sample: which tools are flagged and which are clean.
- The report counts.

## What was not tested

- No real MCP server and no real bank manifest. Only the invented sample.
- No MCP protocol connection. You give it a JSON file.
- The keyword guess for write-like tools will miss some names and flag some harmless ones.
- It reads the schema only. It cannot tell whether a server really enforces the limits it declares.
- Only the Python versions 3.10 and later, and only Python 3.12 in CI.

## Tests

```
pip install pytest
python -m pytest -q
```
