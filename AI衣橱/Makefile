.DEFAULT_GOAL := dev

PYTHON ?= python3.11
VENV_PYTHON := .venv/bin/python
REQUIREMENTS := app/requirements.txt

.PHONY: setup dev dev-backend test test-backend lint lint-backend seed eval share

$(VENV_PYTHON):
	@if command -v "$(PYTHON)" >/dev/null 2>&1; then \
		"$(PYTHON)" -m venv .venv; \
	elif command -v uv >/dev/null 2>&1; then \
		uv venv --python 3.11 --seed .venv; \
	else \
		echo "缺少 Python 3.11；请安装 Python 3.11 或 uv 后重试。" >&2; \
		exit 1; \
	fi

.venv/.requirements-installed: $(REQUIREMENTS) $(VENV_PYTHON)
	@$(VENV_PYTHON) -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else "本项目必须使用 Python 3.11，请检查 .venv。")'
	$(VENV_PYTHON) -m pip install --disable-pip-version-check -r $(REQUIREMENTS)
	@touch "$@"

setup: .venv/.requirements-installed

dev: setup
	@set -eu; \
	command -v node >/dev/null 2>&1 || { echo "缺少 node，请按 AGENTS.md §3.1 检查本机环境。" >&2; exit 1; }; \
	test -f web/node_modules/vite/bin/vite.js || { echo "缺少现有前端依赖，请检查 web/node_modules。" >&2; exit 1; }; \
	backend_pid=; frontend_pid=; \
	cleanup() { \
		trap '' INT TERM; \
		if [ -n "$$backend_pid" ]; then kill -TERM "$$backend_pid" 2>/dev/null || :; fi; \
		if [ -n "$$frontend_pid" ]; then kill -TERM "$$frontend_pid" 2>/dev/null || :; fi; \
		if [ -n "$$backend_pid" ]; then wait "$$backend_pid" 2>/dev/null || :; fi; \
		if [ -n "$$frontend_pid" ]; then wait "$$frontend_pid" 2>/dev/null || :; fi; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	$(VENV_PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app & \
	backend_pid=$$!; \
	(cd web && exec node node_modules/vite/bin/vite.js) & \
	frontend_pid=$$!; \
	while kill -0 "$$backend_pid" 2>/dev/null && kill -0 "$$frontend_pid" 2>/dev/null; do sleep 1; done; \
	result=0; \
	if kill -0 "$$backend_pid" 2>/dev/null; then wait "$$frontend_pid" || result=$$?; \
	else wait "$$backend_pid" || result=$$?; fi; \
	exit "$$result"

dev-backend: setup
	$(VENV_PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

test-backend: setup
	$(VENV_PYTHON) -m pytest -q app/tests

test: test-backend
	cd web && npm test

lint-backend: setup
	$(VENV_PYTHON) -m ruff check app

lint: lint-backend
	cd web && npx tsc --noEmit

seed: setup
	$(VENV_PYTHON) -m scripts.seed

eval: setup
	$(VENV_PYTHON) -m scripts.evaluate

share: setup
	$(VENV_PYTHON) -m scripts.share
