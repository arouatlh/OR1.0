.PHONY: all run test lint docker clean sync

all: run

sync:
	uv sync

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8998 --workers 1 --no-access-log

test:
	uv run pytest -q

lint:
	uv run ruff check .

docker:
	docker build -t astrovitals:latest .

clean:
	rm -rf data/*.db data/*.db-wal data/*.db-shm .pytest_cache .ruff_cache
