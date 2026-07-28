from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

RESOURCE_PACKAGE = "neuroai_workbench.resources.v4_2"


def resource_path(name: str) -> Path:
    target = files(RESOURCE_PACKAGE).joinpath(name)
    with as_file(target) as path:
        return Path(path)


def read_resource_bytes(name: str) -> bytes:
    return files(RESOURCE_PACKAGE).joinpath(name).read_bytes()
