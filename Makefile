PYTHON ?= python

.PHONY: all experiment figures paper manifest test verify

all: experiment figures paper manifest test

experiment:
	$(PYTHON) artifact/run_fault_injection.py

figures:
	$(PYTHON) scripts/generate_figures.py

paper: figures
	$(PYTHON) scripts/build_paper.py

manifest: paper
	$(PYTHON) scripts/build_manifest.py

test:
	$(PYTHON) -m pytest -q

verify: experiment figures paper manifest test
