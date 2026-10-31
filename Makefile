.PHONY: venv install index dev test lint typecheck audit docker demo clean

VENV := .venv
PY := $(VENV)/bin/python

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

install: venv
	$(VENV)/bin/pip install -e ".[dev]"

index:
	$(PY) scripts/build_index.py

dev:
	$(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

test:
	$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check .

typecheck:
	$(VENV)/bin/mypy main.py api core services

audit:
	$(VENV)/bin/pip freeze > /tmp/ecoroute-reqs.txt && $(VENV)/bin/pip-audit -r /tmp/ecoroute-reqs.txt --no-deps

docker:
	docker build -t ecoroute-ai:latest .

demo:
	$(PY) demo/run_demo.py

demo-video:
	$(PY) scripts/make_demo_video.py

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
