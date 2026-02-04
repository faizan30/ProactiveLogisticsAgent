#!/bin/bash
# Start both API and Dashboard

echo "=============================================="
echo "🚀 Starting Proactive Logistics Agent"
echo "=============================================="

# Start uvicorn API in background
uvicorn src.api.main:app --host 0.0.0.0 --port 9001 &
API_PID=$!

# Wait for API to be ready
sleep 2

echo ""
echo "✅ API ready at:        http://localhost:9001"
echo "📖 Swagger docs at:     http://localhost:9001/docs"
echo ""
echo "🎯 Starting Dashboard..."
echo "=============================================="
echo "📊 Dashboard at:        http://localhost:8501"
echo "=============================================="
echo ""

# Start Streamlit dashboard (foreground)
streamlit run scripts/dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
