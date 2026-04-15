#!/bin/bash
# Quick Start Script for Legal Contract Review System Testing

set -e

echo "============================================================"
echo "🚀 Legal Contract Review System - Quick Start"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo "📋 Step 1: Checking Docker Services..."
echo "------------------------------------------------------------"

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
    exit 1
fi

# Check containers
CONTAINERS=$(docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "")

if echo "$CONTAINERS" | grep -q "qdrant"; then
    echo -e "${GREEN}✅ Qdrant is running${NC}"
else
    echo -e "${YELLOW}⚠️  Qdrant is not running${NC}"
fi

if echo "$CONTAINERS" | grep -q "neo4j"; then
    echo -e "${GREEN}✅ Neo4j is running${NC}"
else
    echo -e "${YELLOW}⚠️  Neo4j is not running${NC}"
fi

echo ""
echo "📋 Step 2: Checking Database..."
echo "------------------------------------------------------------"

# Check PostgreSQL
uv run python << 'EOF'
import asyncio
import asyncpg

async def check_db():
    try:
        pool = await asyncpg.create_pool('postgresql://postgres:postgres@localhost:5432/legal_review')
        async with pool.acquire() as conn:
            doc_count = await conn.fetchval('SELECT COUNT(*) FROM legal_documents')
            rel_count = await conn.fetchval('SELECT COUNT(*) FROM document_relationships')
            
            if doc_count > 0:
                print(f"✅ PostgreSQL: {doc_count} documents, {rel_count} relationships")
            else:
                print("⚠️  Database is empty. Run ingestion first.")
        await pool.close()
    except Exception as e:
        print(f"❌ Cannot connect to PostgreSQL: {e}")

asyncio.run(check_db())
EOF

echo ""
echo "📋 Step 3: Starting Backend Server..."
echo "------------------------------------------------------------"
echo -e "${YELLOW}Starting uvicorn on http://localhost:8000...${NC}"
echo -e "${YELLOW}(This will run in the background)${NC}"
echo ""

# Kill existing backend if running
pkill -f "uvicorn apps.review_api.main:app" 2>/dev/null || true
sleep 2

# Start backend in background
nohup uv run uvicorn apps.review_api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   Logs: backend.log"
echo ""

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Backend failed to start. Check backend.log${NC}"
        exit 1
    fi
    sleep 1
done

echo ""
echo "📋 Step 4: Starting Frontend..."
echo "------------------------------------------------------------"

# Check if frontend is already running
if lsof -i:3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Frontend is already running on port 3000${NC}"
    echo "   To restart, kill the existing process first"
else
    echo -e "${YELLOW}Starting Next.js on http://localhost:3000...${NC}"
    echo -e "${YELLOW}(This will run in the background)${NC}"
    echo ""
    
    cd apps/web-app
    
    # Start frontend in background
    nohup npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
    echo "   Logs: apps/web-app/frontend.log"
    echo ""
    
    cd ../..
    
    # Wait for frontend
    echo "⏳ Waiting for frontend to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Frontend is ready!${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Frontend failed to start. Check apps/web-app/frontend.log${NC}"
            exit 1
        fi
        sleep 1
    done
fi

echo ""
echo "============================================================"
echo -e "${GREEN}✅ System is ready for testing!${NC}"
echo "============================================================"
echo ""
echo "📍 Access Points:"
echo "   Frontend:  http://localhost:3000/review"
echo "   Backend:   http://localhost:8000/docs"
echo "   Health:    http://localhost:8000/api/v1/health"
echo "   Neo4j:     http://localhost:7474"
echo ""
echo "📝 Test Contract:"
echo "   Location: test contracts/comprehensive_test_contract.txt"
echo ""
echo "📖 Testing Guide:"
echo "   Location: TESTING_GUIDE.md"
echo ""
echo "🛑 To stop all services:"
echo "   pkill -f 'uvicorn apps.review_api.main:app'"
echo "   pkill -f 'next dev'"
echo ""
echo "🎯 Quick Test:"
echo "   1. Open http://localhost:3000/review"
echo "   2. Copy-paste content from test contract"
echo "   3. Click 'Review Contract'"
echo "   4. Watch the streaming progress"
echo "   5. Click on citations to test expand/collapse"
echo ""
echo "============================================================"
echo "Happy Testing! 🎉"
echo "============================================================"
