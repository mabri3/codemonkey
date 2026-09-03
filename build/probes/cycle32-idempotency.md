# cycle32 idempotency probe
# in-process: same-thread same-call write_file replayed from journal (mtime
# unchanged, replay recorded); miss executes; read-only tools never replayed;
# key stable across dict order, distinct per call-index.
# result: PASS (5/5)
