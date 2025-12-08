FRONTEND_DIR := frontend
BACKEND_DIR := backend
API_URL := http://localhost:8000
VENV_DIR := $(BACKEND_DIR)/.venv

.PHONY: run frontend backend

backend:
	cd $(BACKEND_DIR) && uvicorn app:app --reload --port 8000

frontend:
	cd $(FRONTEND_DIR) && VITE_API_BASE_URL=$(API_URL) npm run dev


venv:
	@echo "Creating virtual environment at $(VENV_DIR)..."
	python3 -m venv $(VENV_DIR)
	@echo "Virtualenv created."

deps:
	@echo "Installing backend Python dependencies..."
	cd $(BACKEND_DIR) && \
		. .venv/bin/activate && \
		pip install -r requirements.txt

	@echo "Installing frontend Node modules..."
	cd $(FRONTEND_DIR) && npm install

	@echo "Dependencies installed."