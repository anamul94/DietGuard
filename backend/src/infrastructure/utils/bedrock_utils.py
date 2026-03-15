"""
Helpers for deterministic chat model initialization.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Sequence

from botocore.config import Config as BotocoreConfig
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import SecretStr

# Default timeout for Bedrock calls. Diet plan generation can take 5-8 min for
# a full 28-meal structured response, so we allow up to 10 minutes.
DEFAULT_READ_TIMEOUT = 600

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = BACKEND_ROOT / ".env"
DEFAULT_MODEL_PROVIDER = "bedrock"
BEDROCK_PROVIDER_CANDIDATES = ("bedrock_converse", "bedrock")
AGENT_NAMES = (
    "diet_plan_agent",
    "daily_summary_agent",
    "food_agent",
    "ingredient_scanner_agent",
    "nutrition_calculator_agent",
    "nutritionist_agent",
    "report_agent",
    "report_merge_agent",
    "summary_agent",
    "test_agent",
)


def _load_backend_env() -> None:
    load_dotenv(dotenv_path=ENV_PATH, override=False)


def _read_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clear_blank_aws_env_vars() -> None:
    for env_name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_SESSION_TOKEN"):
        if os.getenv(env_name, "").strip() == "":
            os.environ.pop(env_name, None)


def _agent_env_key(agent_name: Optional[str], suffix: str) -> Optional[str]:
    if not agent_name:
        return None
    normalized = "".join(ch if ch.isalnum() else "_" for ch in agent_name).upper()
    return f"{normalized}_{suffix}"


def _read_scoped_env(suffix: str, *, agent_name: Optional[str] = None) -> Optional[str]:
    _load_backend_env()

    scoped_key = _agent_env_key(agent_name, suffix)
    if scoped_key:
        scoped_value = _read_env(scoped_key)
        if scoped_value:
            return scoped_value

    return _read_env(suffix)


def _parse_model_reference(
    model: Optional[str], provider: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    if not model:
        return model, provider

    model = model.strip()
    if ":" in model and provider is None:
        maybe_provider, maybe_model = model.split(":", 1)
        if maybe_provider and maybe_model:
            return maybe_model, maybe_provider
    return model, provider


def _normalize_provider(provider: Optional[str]) -> str:
    value = (provider or DEFAULT_MODEL_PROVIDER).strip().lower()
    aliases = {
        "aws_bedrock": "bedrock",
        "bedrock_converse": "bedrock",
    }
    return aliases.get(value, value)


def _provider_candidates(provider: str) -> Sequence[str]:
    if provider == "bedrock":
        return BEDROCK_PROVIDER_CANDIDATES
    return (provider,)


def _coerce_bool(value: Optional[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_debug_max_chars(agent_name: Optional[str] = None) -> int:
    value = _read_scoped_env("LLM_DEBUG_MAX_CHARS", agent_name=agent_name)
    if not value:
        return 4000
    try:
        return max(256, int(value))
    except ValueError:
        return 4000


def is_llm_debug_enabled(agent_name: Optional[str] = None) -> bool:
    return _coerce_bool(_read_scoped_env("LLM_DEBUG_LOG_PROMPTS", agent_name=agent_name))


def _truncate_text(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}... [truncated {len(value) - max_chars} chars]"


def _sanitize_llm_content(value: Any, *, max_chars: int) -> Any:
    if isinstance(value, str):
        return _truncate_text(value, max_chars=max_chars)

    if isinstance(value, list):
        return [_sanitize_llm_content(item, max_chars=max_chars) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_llm_content(item, max_chars=max_chars) for item in value]

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "data" and isinstance(item, str):
                sanitized[key] = f"<redacted {len(item)} chars>"
                continue
            sanitized[key] = _sanitize_llm_content(item, max_chars=max_chars)
        return sanitized

    return value


def build_llm_debug_payload(
    messages: Sequence[dict[str, Any]], *, agent_name: Optional[str] = None
) -> list[dict[str, Any]]:
    max_chars = _get_debug_max_chars(agent_name)
    return [
        {
            "role": message.get("role"),
            "content": _sanitize_llm_content(message.get("content"), max_chars=max_chars),
        }
        for message in messages
    ]


def _build_agent_llm_configs() -> dict[str, dict[str, Optional[str]]]:
    configs: dict[str, dict[str, Optional[str]]] = {}
    for agent in AGENT_NAMES:
        configs[agent] = {
            "model": _read_scoped_env("LLM_MODEL", agent_name=agent),
            "model_provider": _read_scoped_env("LLM_PROVIDER", agent_name=agent),
        }
    return configs


AGENT_LLM_CONFIGS = _build_agent_llm_configs()


def get_agent_llm_config(agent_name: str) -> dict[str, str]:
    settings = AGENT_LLM_CONFIGS.get(agent_name, {})
    return {key: value for key, value in settings.items() if value}


def get_default_model_id() -> str:
    """Resolve the Bedrock model ID using runtime env precedence."""
    _load_backend_env()
    _clear_blank_aws_env_vars()

    explicit_model_id = _read_env("BEDROCK_MODEL_ID")
    if explicit_model_id:
        return explicit_model_id

    inference_profile_id = _read_env("INFERENCE_PROFILE_ID")
    if inference_profile_id:
        return inference_profile_id

    claude_3_7_id = _read_env("CLAUDE_3_7_PROFILE_ID")
    if claude_3_7_id:
        return claude_3_7_id

    return "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"


DEFAULT_BEDROCK_MODEL = get_default_model_id()


def get_bedrock_config() -> dict[str, Any]:
    _load_backend_env()
    _clear_blank_aws_env_vars()

    region_name = _read_env("AWS_REGION") or _read_env("AWS_DEFAULT_REGION")
    credentials_profile_name = _read_env("AWS_PROFILE") or _read_env("AWS_DEFAULT_PROFILE")
    access_key = _read_env("AWS_ACCESS_KEY_ID")
    secret_key = _read_env("AWS_SECRET_ACCESS_KEY")
    session_token = _read_env("AWS_SESSION_TOKEN")

    if access_key and not secret_key:
        raise ValueError("AWS_SECRET_ACCESS_KEY is required when AWS_ACCESS_KEY_ID is set.")
    if secret_key and not access_key:
        raise ValueError("AWS_ACCESS_KEY_ID is required when AWS_SECRET_ACCESS_KEY is set.")
    if access_key and access_key.startswith("ASIA") and not session_token:
        raise ValueError(
            "AWS_SESSION_TOKEN is required when using temporary AWS credentials "
            "(AWS_ACCESS_KEY_ID starts with 'ASIA')."
        )

    # If explicit credentials are present, do not let an ambient AWS profile
    # override them inside boto3/langchain_aws.
    if access_key or secret_key or session_token:
        os.environ.pop("AWS_PROFILE", None)
        os.environ.pop("AWS_DEFAULT_PROFILE", None)
        credentials_profile_name = None

    config: dict[str, Any] = {
        "region_name": region_name,
        "credentials_profile_name": credentials_profile_name,
    }
    if access_key:
        config["aws_access_key_id"] = SecretStr(access_key)
        config["aws_secret_access_key"] = SecretStr(secret_key)
    if session_token:
        config["aws_session_token"] = SecretStr(session_token)

    return {key: value for key, value in config.items() if value is not None}


def get_bedrock_diagnostics(model_id: Optional[str] = None) -> dict[str, Any]:
    """Return non-secret runtime diagnostics for Bedrock configuration."""
    resolved_model_id = model_id or get_default_model_id()
    config = get_bedrock_config()

    access_key = _read_env("AWS_ACCESS_KEY_ID")
    credential_source = "default_chain"
    if config.get("aws_access_key_id"):
        credential_source = "explicit_keys"
    elif config.get("credentials_profile_name"):
        credential_source = "aws_profile"

    credential_type = "not_provided"
    if access_key:
        credential_type = "temporary" if access_key.startswith("ASIA") else "long_lived"

    return {
        "model_id": resolved_model_id,
        "region_name": config.get("region_name"),
        "credential_source": credential_source,
        "credential_type": credential_type,
        "has_session_token": bool(config.get("aws_session_token")),
        "integration_path": "init_chat_model:bedrock_converse",
        "env_path": str(ENV_PATH),
    }


# Central registry for agent LLM config. Model and provider are read from env and cached
# in AGENT_LLM_SETTINGS. Env vars (per-agent overrides take precedence):
#   LLM_MODEL, LLM_PROVIDER          — default for all agents
#   <AGENT>_LLM_MODEL, <AGENT>_LLM_PROVIDER  — e.g. DIET_PLAN_AGENT_LLM_MODEL, FOOD_AGENT_LLM_PROVIDER
# All agents should call create_chat_model(agent_name="...") so they use this central config.
KNOWN_AGENT_NAMES = (
    "test_agent",
    "summary_agent",
    "food_agent",
    "nutritionist_agent",
    "report_agent",
    "report_merge_agent",
    "ingredient_scanner_agent",
    "nutrition_calculator_agent",
    "daily_summary_agent",
    "diet_plan_agent",
)

# Cache: agent_name -> resolved settings from env. Populated by get_agent_llm_settings().
AGENT_LLM_SETTINGS: dict[str, dict[str, Any]] = {}


def resolve_chat_model_settings(
    *,
    agent_name: Optional[str] = None,
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
) -> dict[str, Any]:
    scoped_model = model or _read_scoped_env("LLM_MODEL", agent_name=agent_name)
    scoped_provider = model_provider or _read_scoped_env("LLM_PROVIDER", agent_name=agent_name)
    scoped_model, scoped_provider = _parse_model_reference(scoped_model, scoped_provider)

    normalized_provider = _normalize_provider(scoped_provider)
    resolved_model = scoped_model

    if resolved_model is None and normalized_provider == "bedrock":
        resolved_model = get_default_model_id()

    if resolved_model is None:
        raise ValueError(
            "No chat model configured. Set LLM_MODEL or <AGENT_NAME>_LLM_MODEL for this agent."
        )

    return {
        "agent_name": agent_name,
        "model": resolved_model,
        "model_provider": normalized_provider,
    }


def get_agent_llm_settings(
    *,
    agent_name: Optional[str] = None,
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    Central entry point for agent LLM config. Reads model and provider from env
    (per-agent: <AGENT>_LLM_MODEL / <AGENT>_LLM_PROVIDER, or global LLM_MODEL / LLM_PROVIDER),
    caches in AGENT_LLM_SETTINGS, and returns the resolved settings. Use this (or
    create_chat_model(agent_name=...)) so all agents go through one place.
    """
    if model is not None or model_provider is not None:
        return resolve_chat_model_settings(
            agent_name=agent_name,
            model=model,
            model_provider=model_provider,
        )
    if agent_name and agent_name in AGENT_LLM_SETTINGS:
        return AGENT_LLM_SETTINGS[agent_name]
    settings = resolve_chat_model_settings(agent_name=agent_name)
    if agent_name:
        AGENT_LLM_SETTINGS[agent_name] = settings
    return settings


def get_chat_model_diagnostics(
    *,
    agent_name: Optional[str] = None,
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
) -> dict[str, Any]:
    settings = get_agent_llm_settings(
        agent_name=agent_name,
        model=model,
        model_provider=model_provider,
    )
    diagnostics = {
        "agent_name": settings["agent_name"],
        "model": settings["model"],
        "model_provider": settings["model_provider"],
        "env_path": str(ENV_PATH),
    }

    if settings["model_provider"] == "bedrock":
        diagnostics.update(get_bedrock_diagnostics(settings["model"]))

    return diagnostics


def create_chat_model(
    *,
    agent_name: Optional[str] = None,
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
    temperature: Optional[float] = None,
    read_timeout: int = DEFAULT_READ_TIMEOUT,
    **kwargs: Any,
) -> Any:
    settings = get_agent_llm_settings(
        agent_name=agent_name,
        model=model,
        model_provider=model_provider,
    )

    init_kwargs: dict[str, Any] = dict(kwargs)
    init_kwargs["temperature"] = temperature if temperature is not None else 0

    if settings["model_provider"] == "bedrock":
        config = get_bedrock_config()
        config.update(init_kwargs)
        config["config"] = BotocoreConfig(read_timeout=read_timeout, connect_timeout=10)
        init_kwargs = config

    last_error: Optional[Exception] = None
    for provider_candidate in _provider_candidates(settings["model_provider"]):
        try:
            return init_chat_model(
                model=settings["model"],
                model_provider=provider_candidate,
                **init_kwargs,
            )
        except Exception as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def create_bedrock_chat_model(
    *,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    read_timeout: int = DEFAULT_READ_TIMEOUT,
    **kwargs: Any,
) -> Any:
    return create_chat_model(
        model=model_id,
        model_provider="bedrock",
        temperature=temperature,
        read_timeout=read_timeout,
        **kwargs,
    )


def create_llm(
    *,
    agent_name: str,
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
    temperature: Optional[float] = None,
    read_timeout: int = DEFAULT_READ_TIMEOUT,
    **kwargs: Any,
) -> Any:
    base_settings = get_agent_llm_config(agent_name)
    override_settings = {
        key: value
        for key, value in {"model": model, "model_provider": model_provider}.items()
        if value
    }
    merged_settings = {**base_settings, **override_settings}

    return create_chat_model(
        agent_name=agent_name,
        temperature=temperature,
        read_timeout=read_timeout,
        **merged_settings,
        **kwargs,
    )
