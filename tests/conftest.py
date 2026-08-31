from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from neuroai_workbench.workspace import Workspace

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
EXAMPLES = REPO / "examples" / "assessments"


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace", name="Test workspace")


@pytest.fixture(params=sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.stem)
def example_assessment(request):
    return json.loads(Path(request.param).read_text(encoding="utf-8"))
