VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: help venv install run clean freeze

help:
	@echo "Targets:"
	@echo "  venv    - Create virtualenv in $(VENV) (uses pyenv python if available)"
	@echo "  install - Install requirements into venv"
	@echo "  run     - Run the game via venv python"
	@echo "  freeze  - Export installed packages to requirements.txt"
	@echo "  clean   - Remove venv and Python caches"

$(VENV):
	@# Prefer pyenv's selected Python if present
	@if command -v pyenv >/dev/null 2>&1; then \
		PY=$$(pyenv which python); \
	else \
		PY=$$(command -v python3); \
	fi; \
	$$PY -m venv $(VENV)
	$(PIP) install -U pip

venv: $(VENV)

install: venv
	$(PIP) install -r requirements.txt

doctor: venv
	@$(PY) -c "import tkinter" >/dev/null 2>&1 && echo "Tkinter: OK" || (echo "Tkinter: MISSING"; \
	 echo "Your Python lacks Tk support. See README 'Tkinter setup'."; exit 1)

run: install
	$(PY) main.py

freeze: venv
	$(PIP) freeze > requirements.txt

clean:
	rm -rf $(VENV)
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
