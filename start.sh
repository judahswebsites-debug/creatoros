#!/bin/bash
set -e

echo "=== InstaScope Startup ==="

# Check for .env
if [ ! -f backend/.env ]; then
  echo "⚠️  No backend/.env found. Copying from .env.example..."
  cp backend/.env.example backend/.env
  echo "👉 Edit backend/.env and add your ANTHROPIC_API_KEY, then re-run this script."
  exit 1
fi

# Install backend deps if needed
if [ ! -d backend/venv ]; then
  echo "📦 Creating Python virtual environment..."
  python3 -m venv backend/venv
fi

echo "📦 Installing backend dependencies..."
backend/venv/bin/pip install -q -r backend/requirements.txt

echo "🚀 Starting FastAPI backend on http://localhost:8000 ..."
cd backend
../backend/venv/bin/uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

echo "🌐 Starting frontend on http://localhost:5500 ..."
python3 -m http.server 5500 --directory frontend &
FRONTEND_PID=$!

echo ""
echo "✅ InstaScope is running!"
echo "   Frontend → http://localhost:5500"
echo "   Backend  → http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
