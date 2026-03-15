from langchain_aws import ChatBedrockConverse

from src.infrastructure.utils.bedrock_utils import (
    build_llm_debug_payload,
    create_chat_model,
    create_bedrock_chat_model,
    get_chat_model_diagnostics,
    get_bedrock_config,
    get_bedrock_diagnostics,
    get_default_model_id,
    is_llm_debug_enabled,
    resolve_chat_model_settings,
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


def test_resolve_chat_model_settings_prefers_agent_specific_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("LLM_MODEL", "global-model")
    monkeypatch.setenv("DIET_PLAN_AGENT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DIET_PLAN_AGENT_LLM_MODEL", "gpt-4.1-mini")

    settings = resolve_chat_model_settings(agent_name="diet_plan_agent")

    assert settings["model_provider"] == "openai"
    assert settings["model"] == "gpt-4.1-mini"


def test_create_chat_model_tries_bedrock_provider_aliases(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_PROFILE", "")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTKEY123456789")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("LLM_MODEL", "apac.anthropic.claude-3-7-sonnet-20250219-v1:0")

    calls = []

    def fake_init_chat_model(*, model, model_provider, **kwargs):
        calls.append((model, model_provider, kwargs))
        if model_provider == "bedrock_converse":
            return "ok"
        raise AssertionError("unexpected fallback")

    monkeypatch.setattr("src.infrastructure.utils.bedrock_utils.init_chat_model", fake_init_chat_model)

    llm = create_chat_model(agent_name="diet_plan_agent")

    assert llm == "ok"
    assert calls[0][1] == "bedrock_converse"


def test_get_chat_model_diagnostics_includes_agent_name(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")

    diagnostics = get_chat_model_diagnostics(agent_name="food_agent")

    assert diagnostics["agent_name"] == "food_agent"
    assert diagnostics["model_provider"] == "openai"
    assert diagnostics["model"] == "gpt-4o-mini"


def test_build_llm_debug_payload_redacts_base64_and_truncates(monkeypatch):
    monkeypatch.setenv("LLM_DEBUG_MAX_CHARS", "10")

    payload = build_llm_debug_payload(
        [
            {"role": "user", "content": "abcdefghijklmnopqrstuvwxyz"},
            {
                "role": "user",
                "content": [
                    {"type": "image", "source_type": "base64", "data": "abcd1234"},
                ],
            },
        ]
    )

    assert payload[0]["content"].startswith("abcdefghij")
    assert payload[1]["content"][0]["data"] == "<redacted 8 chars>"


def test_is_llm_debug_enabled_respects_agent_override(monkeypatch):
    monkeypatch.setenv("LLM_DEBUG_LOG_PROMPTS", "false")
    monkeypatch.setenv("DIET_PLAN_AGENT_LLM_DEBUG_LOG_PROMPTS", "true")

    assert is_llm_debug_enabled("diet_plan_agent") is True
