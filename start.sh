#!/bin/bash
# Start both backend and frontend for development

echo "Starting Symposium..."

# Backend
cd "$(dirname "$0")"
pip install -r requirements.txt -q 2>/dev/null
python -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend started on :8000 (PID $BACKEND_PID)"

# Frontend
cd frontend
npm install -q 2>/dev/null
npm run dev &
FRONTEND_PID=$!
echo "Frontend started on :5173 (PID $FRONTEND_PID)"

echo ""
echo "Symposium running at http://localhost:5173"
echo "API docs at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
