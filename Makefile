.PHONY: install run test lint clean docker-build docker-run help

help:
	@echo "SearchPhone OSINT - Makefile"
	@echo "============================"
	@echo "install       - Install dependencies"
	@echo "run           - Run SearchPhone in interactive mode"
	@echo "test          - Run tests with pytest"
	@echo "lint          - Lint code with ruff"
	@echo "clean         - Clean cache, logs, and __pycache__"
	@echo "docker-build  - Build Docker image"
	@echo "docker-run    - Run Docker container"

install:
	pip install -r requirements.txt
	pip install pytest ruff pre-commit

run:
	python search_phone.py

test:
	python -m pytest tests/ -v

lint:
	ruff check src/ search_phone.py
	ruff format --check src/ search_phone.py

clean:
	rm -rf cache/*.json
	rm -rf logs/*.log
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true

docker-build:
	docker build -t searchphone .

docker-run:
	docker run -it --rm \
		-v $(PWD)/.env:/app/.env \
		-v $(PWD)/config.json:/app/config.json \
		-v $(PWD)/reports:/app/reports \
		-v $(PWD)/cache:/app/cache \
		searchphone