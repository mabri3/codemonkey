# cycle31 execution journal probe
# in-process: loop journaling produced intent+outcome records during obsbudget
# runs; kill-safety by design (append-only, fsync-per-line via file close).
# kill -9 test covered in test_journal.py::test_journal_survives_kill9
# result: PASS (unit contract)
