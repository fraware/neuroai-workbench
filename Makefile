PYTHON ?= python
WORKSPACE ?= workspaces/demo

.PHONY: install test verify demo serve build clean
install:
	$(PYTHON) -m pip install -e .[dev]

test:
	$(PYTHON) -m pytest

verify:
	$(PYTHON) scripts/verify_release.py

demo:
	rm -rf $(WORKSPACE)
	neuroai-workbench init $(WORKSPACE) --name "NeuroAI demo workspace"
	neuroai-workbench case-import $(WORKSPACE) examples/PILOT-02_FDA_Adaptive_DBS_v4.2.json

serve:
	neuroai-workbench serve $(WORKSPACE)

build:
	$(PYTHON) -m build

clean:
	rm -rf build dist .pytest_cache src/*.egg-info
