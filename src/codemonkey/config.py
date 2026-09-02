"""Configuration loader for codemonkey.

Precedence (lowest → highest):
  1. defaults
  2. ~/.codemonkey/config.yaml (skipped with ignore_user_config=True)
  3. <cwd>/.codemonkey.yaml
  4. .env files (project dir, then ~/.codemonkey/.env)
  5. process environment variables (CODEMONKEY_*)
  6. CLI flag overrides
"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path

import yaml
from dotenv import dotenv_values

DEFAULTS: dict = {
    "providers": {
        "local": {
            "protocol": "openai",
            "base_url": "http://192.168.50.113:8080/v1",
            "model": "Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf",
            "api_key_env": "CODEMONKEY_API_KEY",
            "tool_protocol": "auto",
        },
        # TEMPORARY (2026-09-02): home llama.cpp (192.168.50.113:8080) is up but
        # its inference path is wedged (verified this tick: /v1/models 200,
        # POST /v1/chat/completions timeouts across 3 prior ticks). This provider
        # exists ONLY to unblock cycle 5's live probes per the autonomous-continue
        # instruction. Remove when the local server recovers.
        "unblock": {
            "protocol": "openai",
            "base_url": "http://127.0.0.1:3458/v1",
            "model": "minimax-m3",
            "api_key_env": "CODEMONKEY_UNBLOCK_KEY",
            "tool_protocol": "auto",
        },
        # TEMPORARY (2026-09-02): second unblock provider — keyless /v1/models,
        # requires Bearer key via CODEMONKEY_UNBLOCK2_KEY for chat. Used for the
        # cycle-9 live probes while home llama.cpp is wedged. Same removal
        # contract as the 3458 `unblock` provider (guard test 6F4 pattern).
        "unblock2": {
            "protocol": "openai",
            "base_url": "http://127.0.0.1:3459/v1",
            "model": "kimi-k2.7-code",
            "api_key_env": "CODEMONKEY_UNBLOCK2_KEY",
            "tool_protocol": "auto",
        },
        "anthropic": {
            "protocol": "anthropic",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-5",
            "api_key_env": "ANTHROPIC_API_KEY",
            "tool_protocol": "native",
        },
    },
    "default_provider": "local",
    "sandbox": "workspace-write",
    "approval": "on-request",
    "max_turns": 30,
    "timeout_seconds": 300,
    "add_dirs": [],
    "web_fetch": False,
    "context_limit": 32000,
    "project_instructions": True,
    "strategies": {
        "compaction": "summarizing",
        "memory": "file",
        "session_state": "jsonl",
    },
}

# Map from env var name → config path
ENV_MAP: dict[str, str] = {
    "CODEMONKEY_PROVIDER": "default_provider",
    "CODEMONKEY_SANDBOX": "sandbox",
    "CODEMONKEY_APPROVAL": "approval",
    "CODEMONKEY_MAX_TURNS": "max_turns",
    "CODEMONKEY_TIMEOUT": "timeout_seconds",
    "CODEMONKEY_TIMEOUT_SECONDS": "timeout_seconds",
    "CODEMONKEY_PROJECT_INSTRUCTIONS": "project_instructions",
    "CODEMONKEY_STRATEGY_COMPACTION": "strategies.compaction",
    "CODEMONKEY_STRATEGY_MEMORY": "strategies.memory",
    "CODEMONKEY_STRATEGY_SESSION_STATE": "strategies.session_state",
}

# Suffix of var name → provider field, e.g. CODEMONKEY_MODEL → providers.<active>.model
PROVIDER_ENV_FIELDS: dict[str, str] = {
    "MODEL": "model",
    "BASE_URL": "base_url",
    "API_KEY": "api_key",
    "TOOL_PROTOCOL": "tool_protocol",
    "PROTOCOL": "protocol",
}
PROVIDER_ENV_PREFIXES = ("CODEMONKEY_", "CODEMONKEY_PROVIDER_")

_KEY_RE = re.compile(r"(?i)(api_?key|token|secret|password)")


class ConfigError(Exception):
    """Exit-2 usage error."""


def _parse_scalar(value: str):
    low = value.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("none", "null"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _set_path(cfg: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _deep_merge(dst: dict, src: dict) -> dict:
    out = copy.deepcopy(dst)
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError) as exc:
        raise ConfigError(f"invalid config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file {path} must be a YAML mapping")
    return data


def _dotenv(paths: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            for key, val in dotenv_values(path).items():
                if val is not None:
                    out[key] = val
    return out


def sanitize(cfg: dict) -> dict:
    """Deep-copy cfg with secret-looking values masked (keys named api_key/token/…
    or values that look like API keys)."""
    out = copy.deepcopy(cfg)

    def bad_value(val) -> bool:
        return isinstance(val, str) and (
            re.search(r"(?i)\bsk-[A-Za-z0-9_-]+", val) is not None or len(val) > 64
        )

    def walk(node):
        if isinstance(node, dict):
            for key, val in node.items():
                pointer = str(key).lower().endswith("_env")
                if (
                    not pointer
                    and _KEY_RE.search(str(key))
                    and isinstance(val, str)
                    and val
                ):
                    node[key] = "***"
                elif bad_value(val):
                    node[key] = "***"
                else:
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(out)
    return out


def resolve_api_key(cfg: dict, provider: str | None = None) -> str | None:
    name = provider or cfg.get("default_provider", "local")
    pconf = cfg.get("providers", {}).get(name, {})
    key = pconf.get("api_key")
    if key:
        return key
    env_name = pconf.get("api_key_env")
    if env_name:
        return os.environ.get(env_name)
    return None


# Known strategy names per domain (cycle 7 provides the real strategy
# implementations / registries; names are canonicalized here so validation
# works from cycle 1 onward).
KNOWN_STRATEGIES: dict[str, list[str]] = {
    "compaction": ["summarizing", "sliding-window"],
    "memory": ["file", "none"],
    "session_state": ["jsonl", "sqlite"],
}

_ENUMS: dict[str, list] = {
    "sandbox": ["read-only", "workspace-write", "danger-full-access"],
    "approval": ["untrusted", "on-request", "never"],
}


def _validate_strategies(strategies: dict) -> None:
    for domain, valid in KNOWN_STRATEGIES.items():
        name = strategies.get(domain)
        if name is None:
            continue
        if name not in valid:
            raise ConfigError(
                f"unknown strategy '{name}' for '{domain}'. "
                f"Valid {domain} strategies: {', '.join(valid)}"
            )


def _validate(cfg: dict) -> None:
    if not isinstance(cfg.get("providers"), dict) or not cfg["providers"]:
        raise ConfigError("config must define at least one provider")
    default = cfg.get("default_provider", "local")
    if default not in cfg["providers"]:
        raise ConfigError(
            f"default_provider '{default}' is not defined. "
            f"Valid providers: {', '.join(cfg['providers'])}"
        )
    for enum_field, allowed in _ENUMS.items():
        val = cfg.get(enum_field)
        if val not in allowed:
            raise ConfigError(
                f"invalid {enum_field} '{val}'. Valid values: {', '.join(allowed)}"
            )
    for pname, pconf in cfg["providers"].items():
        proto = pconf.get("protocol", "openai")
        if proto not in ("openai", "anthropic"):
            raise ConfigError(
                f"provider '{pname}' has invalid protocol '{proto}' "
                "(openai | anthropic)"
            )
        tp = pconf.get("tool_protocol", "auto")
        if tp not in ("auto", "native", "prompt"):
            raise ConfigError(
                f"provider '{pname}' has invalid tool_protocol '{tp}' "
                "(auto | native | prompt)"
            )
    _validate_strategies(cfg.get("strategies", {}) or {})


def load_config(
    cwd: Path | None = None,
    overrides: dict | None = None,
    ignore_user_config: bool = False,
) -> dict:
    """Merge defaults → user YAML → project YAML → .env → env vars → overrides.

    Returns a raw (unsanitized) config dict. Raises ConfigError on bad files or
    invalid strategy/enum values.
    """
    cwd = Path(cwd or Path.cwd()).resolve()
    cfg = copy.deepcopy(DEFAULTS)

    if not ignore_user_config:
        cfg = _deep_merge(cfg, _load_yaml(Path.home() / ".codemonkey" / "config.yaml"))
    cfg = _deep_merge(cfg, _load_yaml(cwd / ".codemonkey.yaml"))

    # .env files then real env
    env: dict[str, str] = _dotenv(
        [cwd / ".env", Path.home() / ".codemonkey" / ".env"]
    )
    env.update(os.environ)

    # Split into generic settings and provider-specific ones.
    prov_env: dict[str, dict[str, str]] = {}  # provider → field → value
    for key, val in env.items():
        if not key.startswith("CODEMONKEY_"):
            continue
        if key in ENV_MAP:
            _set_path(cfg, ENV_MAP[key], _parse_scalar(val))
            continue
        for prefix in PROVIDER_ENV_PREFIXES:
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            # Try direct provider field (MODEL / BASE_URL / …)
            if rest in PROVIDER_ENV_FIELDS:
                prov_env.setdefault("__active__", {})[PROVIDER_ENV_FIELDS[rest]] = val
                break
            # Try PROVIDER_FIELD form (LOCAL_MODEL, ANTHROPIC_BASE_URL, …)
            m = re.match(
                rf"^(.+?)_({'|'.join(PROVIDER_ENV_FIELDS)})$", rest
            )
            if m:
                prov = m.group(1).lower().replace("_", "-")
                field = PROVIDER_ENV_FIELDS[m.group(2)]
                prov_env.setdefault(prov, {})[field] = val
                break

    for prov, fields in prov_env.items():
        if prov == "__active__":
            active = cfg.get("default_provider", "local")
        else:
            active = prov
        providers = cfg.setdefault("providers", {})
        if active not in providers:
            providers[active] = {}
        for field, val in fields.items():
            providers[active][field] = _parse_scalar(val) if field != "api_key" else val

    if overrides:
        for key, value in overrides.items():
            if value is None:
                continue
            _set_path(cfg, key, value)

    _validate(cfg)
    return cfg


def _yaml_dump(data) -> str:
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


def render_config(cfg: dict, sanitize_secrets: bool = True) -> str:
    data = sanitize(cfg) if sanitize_secrets else cfg
    return "---\n" + _yaml_dump(data)
