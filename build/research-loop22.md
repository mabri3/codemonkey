# Loop 22 Research — Plan-Preview Dry Run (CYCLE R22)

Date: 2026-09-03 · Method: live search (1 query) — consistent with the
preview/confirm/apply pattern family.

## Finding
Exec-level `--dry-run`: intercept mutating tools (write_file/edit_file/shell)
at the approval gate; return a PREVIEW payload (would-be diff for file tools,
command + approval verdict for shell) instead of executing. The model sees
"DRY-RUN (not executed)" and can revise; operators get an auditable plan.

## SELECTED
1. **CYCLE 59 — exec --dry-run**: mutating calls return formatted previews
   (write: byte counts + first lines; edit: SREP search/replace lengths;
   shell: command only), journal records type=preview, run fully otherwise.
   verify: unit (≥5 tests: write preview, edit preview, shell preview,
   read tools pass through, journal preview record).
