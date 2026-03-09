#!/bin/bash
# start_antigravity.sh — Start Antigravity with CDP debug port and bridge server
# Run on macOS/Linux: bash start_antigravity.sh

CDP_PORT=9229
BRIDGE_PORT=19999
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANTIGRAVITY_LOG=${ANTIGRAVITY_LOG:-/tmp/antigravity-cdp.log}

# Kill existing instances
killall mitmdump 2>/dev/null
pkill -f 'antigravity_bridge\|bridge.py.*19999' 2>/dev/null

is_cdp_ready() {
    curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1
}

stop_antigravity() {
    case "$(uname -s)" in
        Darwin)
            osascript -e 'tell application "Antigravity" to quit' 2>/dev/null || true
            ;;
        *)
            pkill -x antigravity 2>/dev/null || true
            pkill -f '/usr/share/antigravity/antigravity' 2>/dev/null || true
            ;;
    esac
}

start_antigravity() {
    case "$(uname -s)" in
        Darwin)
            if ! command -v open >/dev/null 2>&1; then
                echo "❌ macOS launcher 'open' not found"
                return 1
            fi
            open -a Antigravity --args --remote-debugging-port="$CDP_PORT"
            ;;
        *)
            if command -v antigravity >/dev/null 2>&1; then
                nohup antigravity --remote-debugging-port="$CDP_PORT" \
                    >"$ANTIGRAVITY_LOG" 2>&1 &
            else
                echo "❌ 'antigravity' launcher not found in PATH"
                echo "   Install Antigravity or set PATH so the launcher is available."
                return 1
            fi
            ;;
    esac
}

wait_for_cdp() {
    for _ in $(seq 1 20); do
        if is_cdp_ready; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Check if Antigravity is running with debug port
if ! is_cdp_ready; then
    echo "Starting Antigravity with --remote-debugging-port=$CDP_PORT ..."
    stop_antigravity
    sleep 3
    start_antigravity || exit 1

    if wait_for_cdp; then
        echo "✅ Antigravity started with CDP on port $CDP_PORT"
    else
        echo "❌ Failed to start Antigravity with CDP"
        if [ -f "$ANTIGRAVITY_LOG" ]; then
            echo ""
            echo "Last launcher log lines:"
            tail -n 20 "$ANTIGRAVITY_LOG"
        fi
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
