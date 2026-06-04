#!/bin/bash
cd "$(dirname "$0")/backend"
echo "🚀 Starting EduGuard AI Backend..."
echo ""
echo "📋 Installing dependencies..."
pip install -r requirements.txt -q
echo ""
echo "🤖 Starting server at http://localhost:8000"
echo "📖 API Docs: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
