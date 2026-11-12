#!/bin/bash
# start_antigravity.sh — Start Antigravity with CDP debug port and bridge server
# Run on Mac: bash start_antigravity.sh

CDP_PORT=9229
BRIDGE_PORT=19999
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill existing instances
pkill -f "bridge.py --port $BRIDGE_PORT" 2>/dev/null

# Check if Antigravity is running with debug port
if ! curl -s http://127.0.0.1:$CDP_PORT/json/version >/dev/null 2>&1; then
    echo "Starting Antigravity with --remote-debugging-port=$CDP_PORT ..."
    osascript -e 'tell application "Antigravity" to quit' 2>/dev/null
    sleep 3
    open -a Antigravity --args --remote-debugging-port=$CDP_PORT
    sleep 5
    
    if curl -s http://127.0.0.1:$CDP_PORT/json/version >/dev/null 2>&1; then
        echo "✅ Antigravity started with CDP on port $CDP_PORT"
    else
        echo "❌ Failed to start Antigravity with CDP"
        exit 1
    fi
else
    echo "✅ Antigravity already running with CDP on port $CDP_PORT"
fi

# Start bridge
echo "Starting bridge on port $BRIDGE_PORT ..."
nohup python3 "$SCRIPT_DIR/bridge.py" --port $BRIDGE_PORT --cdp-port $CDP_PORT \
    > /tmp/ag_bridge.log 2>&1 &
echo "Bridge PID: $!"

sleep 2
if curl -s http://127.0.0.1:$BRIDGE_PORT/health | grep -q '"ok"'; then
    echo "✅ Bridge healthy on port $BRIDGE_PORT"
    echo ""
    echo "Usage:"
    echo "  curl http://localhost:$BRIDGE_PORT/models"
    echo '  curl -X POST http://localhost:'$BRIDGE_PORT'/chat -d '"'"'{"prompt":"hello"}'"'"''
    echo '  curl -X POST http://localhost:'$BRIDGE_PORT'/model -d '"'"'{"model":"Claude Opus 4.6 (Thinking)"}'"'"''
else
    echo "❌ Bridge failed to start"
    cat /tmp/ag_bridge.log
    exit 1
fi
