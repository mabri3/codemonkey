# cycle27 repo-map relevance probe
# git fixture: stale.py most recent commit, relevant.py older but symbol-matching;
# query_terms=["parser_tool"] lifts relevant.py ahead of stale.py (recency overridden);
# non-matching query falls back to cycle-21 order; budget enforced with relevance;
# injection byte-identical across two calls.
# result: PASS (5/5 tests)
