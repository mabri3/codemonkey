# cycle47 availability failover probe
# transport/timeout -> fallback_provider re-run (journal route-switch record);
# auth + tools-500 never fail over; unknown fallback provider fail-closed at
# exec start; retry-exhaustion precondition (retries happen inside provider
# before the switch).
# result: PASS (5/5; HOME/config isolation via cfg_mod patch — exec imports
# load_config per-call from .config, so cfg_mod attribute patch is required)
