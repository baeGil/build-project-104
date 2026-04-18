#!/bin/bash
# Start Next.js development server with clean logging

echo ""
echo "========================================"
echo "🚀 Starting Vietnamese Legal AI Frontend"
echo "========================================"
echo ""

# Set environment variables to reduce noise
export NODE_ENV=development
export NEXT_TELEMETRY_DISABLED=1

# Start Next.js
npm run dev
