PYTHON ?= python
FRAMEWORK_PYTHON ?= .venv-frameworks/bin/python

.PHONY: all experiment framework-probe-verify figures paper manifest test verify

all: experiment framework-probe-verify figures paper manifest test

experiment:
	$(PYTHON) artifact/run_fault_injection.py

framework-probe-verify:
	$(PYTHON) scripts/build_framework_replay_receipt.py --python $(FRAMEWORK_PYTHON)

figures:
	$(PYTHON) scripts/generate_figures.py

paper: figures
	$(PYTHON) scripts/build_paper.py

manifest: paper
	$(PYTHON) scripts/build_manifest.py

test:
	$(PYTHON) -m pytest -q

verify: experiment framework-probe-verify figures paper manifest test
