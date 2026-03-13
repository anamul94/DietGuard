from langchain_aws import ChatBedrockConverse

from src.infrastructure.utils.bedrock_utils import (
    create_bedrock_chat_model,
    get_bedrock_config,
    get_bedrock_diagnostics,
    get_default_model_id,
)


def test_get_bedrock_config_prefers_explicit_keys_over_profile(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_PROFILE", "stale-profile")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTKEY123456789")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")

    config = get_bedrock_config()

    assert config["region_name"] == "ap-south-1"
    assert "credentials_profile_name" not in config
    assert config["aws_access_key_id"].get_secret_value() == "AKIATESTKEY123456789"
    assert config["aws_secret_access_key"].get_secret_value() == "test-secret"


def test_get_bedrock_config_requires_session_token_for_temporary_credentials(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_PROFILE", "")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIATEMPKEY123456789")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")

    try:
        get_bedrock_config()
        raised = False
    except ValueError as exc:
        raised = True
        assert "AWS_SESSION_TOKEN is required" in str(exc)

    assert raised


def test_get_default_model_id_uses_explicit_override(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("INFERENCE_PROFILE_ID", "apac.anthropic.claude-3-7-sonnet-20250219-v1:0")

    assert get_default_model_id() == "global.anthropic.claude-sonnet-4-6"
    assert get_bedrock_diagnostics()["model_id"] == "global.anthropic.claude-sonnet-4-6"


def test_create_bedrock_chat_model_uses_init_chat_model_bedrock_converse(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_PROFILE", "")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTKEY123456789")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "apac.anthropic.claude-3-7-sonnet-20250219-v1:0")

    llm = create_bedrock_chat_model()

    assert isinstance(llm, ChatBedrockConverse)
    assert llm.model_id == "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"
