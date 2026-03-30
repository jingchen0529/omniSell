backend-install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

backend-dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

backend-worker:
	cd backend && . .venv/bin/activate && python -m app.worker

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev
