import json
import logging
import uuid

from src.application.services.hipaa_audit_service import _coerce_uuid
from src.infrastructure.utils.logger import CloudWatchFormatter


class StringableUUID:
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value


def test_coerce_uuid_accepts_native_and_stringable_uuid_values():
    value = uuid.uuid4()

    assert _coerce_uuid(value) == value
    assert _coerce_uuid(str(value)) == value
    assert _coerce_uuid(StringableUUID(str(value))) == value


def test_cloudwatch_formatter_serializes_uuid_extra_fields():
    user_id = uuid.uuid4()
    record = logging.LogRecord(
        name="dietguard-backend",
        level=logging.ERROR,
        pathname=__file__,
        lineno=12,
        msg="uuid log",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"user_id": user_id, "nested": {"patient_user_id": user_id}}

    payload = json.loads(CloudWatchFormatter().format(record))

    assert payload["user_id"] == str(user_id)
    assert payload["nested"]["patient_user_id"] == str(user_id)
