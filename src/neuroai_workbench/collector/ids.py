from __future__ import annotations

from uuid import uuid4


def new_request_id() -> str:
    return f"CREQ-{uuid4().hex}"


def new_result_id() -> str:
    return f"CRES-{uuid4().hex}"


def new_failure_id() -> str:
    return f"CFAIL-{uuid4().hex}"


def new_quarantine_id() -> str:
    return f"QRN-{uuid4().hex}"
