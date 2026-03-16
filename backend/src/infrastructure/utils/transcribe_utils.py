from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import boto3
import httpx
from dotenv import load_dotenv

import re

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".m4a": "mp4",  # m4a is an MP4 container in practice
}


class TranscribeConfigError(RuntimeError):
    pass


class TranscribeFailedError(RuntimeError):
    pass


BACKEND_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = BACKEND_ROOT / ".env"


def _load_backend_env() -> None:
    # Ensure local development picks up backend/.env even if the process
    # is started from the repo root.
    load_dotenv(dotenv_path=ENV_PATH, override=False)


def _read_env(name: str) -> Optional[str]:
    _load_backend_env()
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clear_blank_aws_env_vars() -> None:
    # Keep parity with bedrock_utils: blank AWS_PROFILE can cause boto3 to
    # attempt to resolve a profile with an empty name.
    for env_name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_SESSION_TOKEN"):
        if os.getenv(env_name, "").strip() == "":
            os.environ.pop(env_name, None)


def _read_env_int(name: str, default: int) -> int:
    raw = (_read_env(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_max_mood_audio_bytes() -> int:
    max_mb = _read_env_int("MAX_MOOD_AUDIO_MB", 12)
    return max(1, max_mb) * 1024 * 1024


def infer_transcribe_media_format(filename: str) -> Optional[str]:
    lowered = (filename or "").lower()
    for ext, fmt in SUPPORTED_AUDIO_EXTENSIONS.items():
        if lowered.endswith(ext):
            return fmt
    return None


def _get_transcribe_bucket() -> str:
    bucket = (_read_env("TRANSCRIBE_S3_BUCKET") or "").strip()
    if not bucket:
        raise TranscribeConfigError("TRANSCRIBE_S3_BUCKET is required for mood check-in transcription.")
    return bucket


def _get_transcribe_prefix() -> str:
    prefix = (_read_env("TRANSCRIBE_S3_PREFIX") or "mood-checkins/").strip()
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _get_transcribe_language_code() -> str:
    return (_read_env("TRANSCRIBE_LANGUAGE_CODE") or "en-US").strip() or "en-US"


def _get_aws_region() -> str:
    region = _read_env("AWS_REGION") or _read_env("AWS_DEFAULT_REGION") or "ap-south-1"
    return region.strip() or "ap-south-1"


def _get_transcribe_timeout_seconds() -> int:
    return max(30, _read_env_int("TRANSCRIBE_TIMEOUT_SECONDS", 180))


def _get_transcribe_poll_interval_seconds() -> float:
    raw = (_read_env("TRANSCRIBE_POLL_INTERVAL_SECONDS") or "2").strip()
    try:
        return max(0.5, float(raw))
    except ValueError:
        return 2.0


@dataclass(frozen=True)
class TranscriptionResult:
    transcript_text: str
    job_name: str
    media_format: str
    s3_object_key: str


def _s3_client():
    _load_backend_env()
    _clear_blank_aws_env_vars()

    profile = _read_env("AWS_PROFILE") or _read_env("AWS_DEFAULT_PROFILE")
    access_key = _read_env("AWS_ACCESS_KEY_ID")
    secret_key = _read_env("AWS_SECRET_ACCESS_KEY")
    session_token = _read_env("AWS_SESSION_TOKEN")

    region_name = _get_aws_region()
    if profile and (access_key or secret_key or session_token):
        # Avoid ambiguous config; boto3 may behave unexpectedly if both are set.
        raise TranscribeConfigError("Use either AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, not both.")

    if access_key and not secret_key:
        raise TranscribeConfigError("AWS_SECRET_ACCESS_KEY is required when AWS_ACCESS_KEY_ID is set.")
    if secret_key and not access_key:
        raise TranscribeConfigError("AWS_ACCESS_KEY_ID is required when AWS_SECRET_ACCESS_KEY is set.")
    if access_key and not re.fullmatch(r"AKIA[0-9A-Z]{16}", access_key):
        raise TranscribeConfigError("AWS_ACCESS_KEY_ID is not in the expected format (AKIA...).")
    if secret_key and not re.fullmatch(r"[0-9A-Za-z/+=]{40}", secret_key):
        raise TranscribeConfigError("AWS_SECRET_ACCESS_KEY is not in the expected 40-character format.")
    if access_key and access_key.startswith("ASIA") and not session_token:
        raise TranscribeConfigError("AWS_SESSION_TOKEN is required for temporary credentials (ASIA...).")

    if profile:
        session = boto3.Session(profile_name=profile, region_name=region_name)
        return session.client("s3", region_name=region_name)
    if access_key and secret_key:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region_name,
        )
        return session.client("s3", region_name=region_name)

    # Fallback to boto3's standard resolution chain (e.g., ECS/EC2 role).
    return boto3.client("s3", region_name=region_name)


def _transcribe_client():
    _load_backend_env()
    _clear_blank_aws_env_vars()
    region_name = _get_aws_region()
    return boto3.client("transcribe", region_name=region_name)


def _make_s3_object_key(filename: str) -> str:
    ext = ""
    lowered = (filename or "").lower()
    for candidate in SUPPORTED_AUDIO_EXTENSIONS.keys():
        if lowered.endswith(candidate):
            ext = candidate
            break
    return f"{_get_transcribe_prefix()}{uuid.uuid4().hex}{ext}"


def _put_object(bucket: str, key: str, data: bytes, content_type: Optional[str] = None) -> None:
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": data}
    if content_type:
        kwargs["ContentType"] = content_type
    _s3_client().put_object(**kwargs)


def _delete_object(bucket: str, key: str) -> None:
    _s3_client().delete_object(Bucket=bucket, Key=key)


def _start_job(*, job_name: str, media_uri: str, media_format: str, language_code: str) -> None:
    _transcribe_client().start_transcription_job(
        TranscriptionJobName=job_name,
        LanguageCode=language_code,
        MediaFormat=media_format,
        Media={"MediaFileUri": media_uri},
    )


def _get_job(job_name: str) -> dict[str, Any]:
    return _transcribe_client().get_transcription_job(TranscriptionJobName=job_name)


def _extract_transcript_text(payload: dict[str, Any]) -> str:
    # AWS Transcribe has a few output shapes. Prefer the pre-built transcript if present,
    # otherwise reconstruct from items. Never log or return partials here; the caller can
    # handle error mapping.

    results = payload.get("results") or payload.get("Results") or {}
    if not isinstance(results, dict):
        raise TranscribeFailedError(f"Transcript payload missing results. keys={sorted(payload.keys())}")

    transcripts = results.get("transcripts") or results.get("Transcripts") or []
    if isinstance(transcripts, list):
        empty_transcript_seen = False
        for item in transcripts:
            if not isinstance(item, dict):
                continue
            text = (
                item.get("transcript")
                or item.get("Transcript")
                or item.get("text")
                or item.get("Text")
            )
            if isinstance(text, list):
                # Rare: some wrappers may place transcript fragments into a list.
                text = " ".join(str(part).strip() for part in text if str(part).strip())
            if isinstance(text, str) and text.strip():
                return text.strip()
            if isinstance(text, str) and not text.strip():
                empty_transcript_seen = True

        # If Transcribe produced a transcript field but it's empty and there are no
        # item-level tokens, treat this as "no speech detected".
        if empty_transcript_seen:
            raise TranscribeFailedError("Empty transcript text (no speech detected).")

    # Fallback: build from items.
    items = results.get("items") or results.get("Items") or []
    if isinstance(items, list) and items:
        parts: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            alternatives = item.get("alternatives") or item.get("Alternatives") or []
            if isinstance(alternatives, dict):
                alternatives = [alternatives]
            if not alternatives or not isinstance(alternatives, list):
                continue
            first = alternatives[0] if alternatives else None
            content = (first or {}).get("content") if isinstance(first, dict) else None
            if content is None and isinstance(first, dict):
                content = first.get("Content")
            if not isinstance(content, str) or not content:
                continue
            item_type = (item.get("type") or item.get("Type") or "").lower()
            if item_type == "punctuation":
                # Attach punctuation to previous token.
                if parts:
                    parts[-1] = f"{parts[-1]}{content}"
                else:
                    parts.append(content)
            else:
                parts.append(content)

        combined = " ".join(parts).strip()
        if combined:
            return combined

    transcript_count = len(transcripts) if isinstance(transcripts, list) else 0
    item_count = len(items) if isinstance(items, list) else 0
    sample_transcript_keys: list[str] = []
    if isinstance(transcripts, list) and transcripts and isinstance(transcripts[0], dict):
        sample_transcript_keys = sorted(transcripts[0].keys())
    sample_item_keys: list[str] = []
    sample_alt_keys: list[str] = []
    if isinstance(items, list) and items and isinstance(items[0], dict):
        sample_item_keys = sorted(items[0].keys())
        alternatives0 = items[0].get("alternatives") if isinstance(items[0], dict) else None
        if isinstance(alternatives0, list) and alternatives0 and isinstance(alternatives0[0], dict):
            sample_alt_keys = sorted(alternatives0[0].keys())

    summary = (
        "Transcript JSON did not contain transcript text. "
        f"payload_keys={sorted(payload.keys())} results_keys={sorted(results.keys())} "
        f"transcripts={transcript_count} items={item_count} "
        f"sample_transcript_keys={sample_transcript_keys} sample_item_keys={sample_item_keys} sample_alt_keys={sample_alt_keys}"
    )
    raise TranscribeFailedError(summary)


async def transcribe_audio_bytes(
    *,
    filename: str,
    content_type: Optional[str],
    audio_bytes: bytes,
) -> TranscriptionResult:
    media_format = infer_transcribe_media_format(filename)
    if not media_format:
        raise ValueError("Unsupported audio format.")

    bucket = _get_transcribe_bucket()
    key = _make_s3_object_key(filename)
    job_name = f"moodcheckin-{uuid.uuid4().hex}"
    language_code = _get_transcribe_language_code()
    timeout_seconds = _get_transcribe_timeout_seconds()
    poll_interval = _get_transcribe_poll_interval_seconds()

    # Always clean up the S3 object, even if transcription fails.
    await asyncio.to_thread(_put_object, bucket, key, audio_bytes, content_type)
    try:
        media_uri = f"s3://{bucket}/{key}"
        await asyncio.to_thread(
            _start_job,
            job_name=job_name,
            media_uri=media_uri,
            media_format=media_format,
            language_code=language_code,
        )

        deadline = time.time() + timeout_seconds
        status = "IN_PROGRESS"
        job: dict[str, Any] = {}
        while time.time() < deadline:
            job = await asyncio.to_thread(_get_job, job_name)
            details = (job or {}).get("TranscriptionJob") or {}
            status = (details.get("TranscriptionJobStatus") or "").upper()
            if status in {"COMPLETED", "FAILED"}:
                break
            await asyncio.sleep(poll_interval)

        if status != "COMPLETED":
            reason = ""
            try:
                reason = (
                    ((job or {}).get("TranscriptionJob") or {})
                    .get("FailureReason")
                    or ""
                )
            except Exception:
                reason = ""
            raise TranscribeFailedError(f"Transcription did not complete. status={status} reason={reason}".strip())

        transcript_uri = (
            ((job or {}).get("TranscriptionJob") or {})
            .get("Transcript", {})
            .get("TranscriptFileUri")
        )
        if not transcript_uri:
            raise TranscribeFailedError("Transcription job completed but TranscriptFileUri was missing.")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(transcript_uri)
            resp.raise_for_status()
            payload = resp.json()

        transcript_text = _extract_transcript_text(payload)
        if not transcript_text.strip():
            raise TranscribeFailedError("Empty transcript text (no speech detected).")
        return TranscriptionResult(
            transcript_text=transcript_text,
            job_name=job_name,
            media_format=media_format,
            s3_object_key=key,
        )
    finally:
        # Privacy: delete audio from S3 immediately after the attempt.
        try:
            await asyncio.to_thread(_delete_object, bucket, key)
        except Exception:
            # Best-effort cleanup; bucket lifecycle policy should backstop this.
            pass
