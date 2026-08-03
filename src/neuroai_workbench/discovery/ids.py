from __future__ import annotations

from uuid import uuid4


def new_run_id() -> str:
    return f"DRUN-{uuid4().hex}"


def new_proposal_id() -> str:
    return f"DSP-{uuid4().hex}"


def new_adjudication_id() -> str:
    return f"DADJ-{uuid4().hex}"


def new_successor_id() -> str:
    return f"DRS-{uuid4().hex}"
