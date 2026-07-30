
PYTHON ?= python
WORKSPACE ?= workspaces/demo
ARTIFACTS ?= artifacts

.PHONY: install quality test verify demo serve package audit clean

install:
	$(PYTHON) -m pip install -e .[dev]

quality:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy src/neuroai_workbench
	$(PYTHON) -m compileall -q src scripts
	$(PYTHON) scripts/check_repository_hygiene.py
	$(PYTHON) scripts/check_version_consistency.py
	$(PYTHON) scripts/agent_eval_harness.py

test:
	$(PYTHON) -m pytest --cov=neuroai_workbench --cov-report=term-missing --cov-fail-under=90

verify:
	mkdir -p $(ARTIFACTS)
	$(PYTHON) scripts/verify_release.py --output $(ARTIFACTS)/RELEASE_VERIFICATION.json

package:
	rm -rf build dist
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*

audit:
	$(PYTHON) -m pip_audit

demo:
	rm -rf $(WORKSPACE)
	neuroai-workbench init $(WORKSPACE) --name "NeuroAI demo workspace"
	neuroai-workbench case-import $(WORKSPACE) examples/assessments/PILOT-02_FDA_Adaptive_DBS_v4.2.json

serve:
	neuroai-workbench serve $(WORKSPACE)

clean:
	rm -rf artifacts build dist .coverage .pytest_cache htmlcov src/*.egg-info workspaces
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
