"""
Helpers for deterministic Bedrock client initialization.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import SecretStr

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = BACKEND_ROOT / ".env"


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


def create_bedrock_chat_model(
    *,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs: Any,
) -> Any:
    if model_id is None:
        model_id = get_default_model_id()

    config = get_bedrock_config()
    config.update(kwargs)

    final_temperature = temperature if temperature is not None else 0

    return init_chat_model(
        model=model_id,
        model_provider="bedrock_converse",
        temperature=final_temperature,
        **config,
    )
