# cycle20 repo_map probe — 2026-09-02T11:33:06.606038
# 1) live exec: model asked which file defines parse_tool_calls -> answered
#    "src/codemonkey/protocol.py" (correct).
# 2) in-process forced tool use: tool.started repo_map -> TOOL_RESULT repo_map
#    delivered, result contains protocol.py (symbols + lines).
# 3) cache: second scan with unchanged mtime does not re-enter the scanner
#    (unit test asserts spy count 0); touching one file invalidates only it.
# results: PASS
