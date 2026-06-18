# @Author suke
# @Date 2026-06-16 14:30:25
# @Desc pyknp 项目主入口 — 测试、lint、启动、清理统一收口

.PHONY: help setup test test-unit test-integration test-e2e test-all \
        test-coverage golden-update lint format typecheck run clean

help:  ## 列出所有 target
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup:  ## 安装全部依赖
	uv sync

test:  ## 单元 + 集成测试
	uv run pytest tests/unit tests/integration tests/api tests/storage tests/rules -v

test-unit:  ## 仅单元测试
	uv run pytest tests/unit -v

test-integration:  ## 仅集成测试
	uv run pytest tests/integration tests/api tests/storage tests/rules -v

test-e2e:  ## 仅 E2E 测试
	uv run pytest tests/e2e -v

test-all: test test-e2e  ## 全量测试

test-coverage:  ## 全量 + 100% 覆盖率（line + branch）
	uv run pytest --cov=src/pyknp --cov-branch --cov-fail-under=100 --cov-report=term-missing

golden-update:  ## 刷新 E2E golden 快照
	uv run pytest tests/e2e --update-golden

lint:  ## ruff 静态检查
	uv run ruff check src/ tests/

format:  ## ruff 自动格式化
	uv run ruff format src/ tests/

typecheck:  ## mypy 类型检查
	uv run mypy src/pyknp

run:  ## 启动开发服务器（仅监听 src/ 变更，避免上传解压触发 reload）
	uv run uvicorn pyknp.app:app --reload --reload-dir src --port 8000

clean:  ## 清理缓存与运行产物
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache
	rm -f data/runs/*.json data/index.json
	rm -rf data/uploads/*
	@touch data/uploads/.gitkeep data/runs/.gitkeep
