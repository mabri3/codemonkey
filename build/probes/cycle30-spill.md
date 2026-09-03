# cycle30 tool-result spill probe
# unit: 6/6 — verbatim spill, marker path exists+retrievable via read_file
# slice (L01500), under-budget untouched, prune, head+tail shape
# LIVE: spill files created by the loop's budget path during obsbudget tests
# (~/.codemonkey/spill/*-shell-*.txt, verbatim AAA/BBB fixtures);
# seq-3000 live probe BLOCKED-slow (home 27B can't finish the tool loop inside
# 360s; same hardware limit as A9 in loop5-final — recorded honestly)
# result: PASS (unit contract + in-process spill evidence)
