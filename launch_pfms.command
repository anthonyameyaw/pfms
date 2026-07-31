#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    osascript -e 'display alert "Python 3 not found" message "Please install from python.org" as critical'
    exit 1
fi

python3 -c "import flask" 2>/dev/null || {
    echo "Installing Flask..."
    pip3 install flask --break-system-packages -q
}

lsof -ti:5000 | xargs kill -9 2>/dev/null
sleep 1

echo "Starting Palm Farm Management System..."
echo "Waiting for server..."

python3 app.py &
FLASK_PID=$!

for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/ 2>/dev/null | grep -q "200"; then
        echo "Server ready!"
        break
    fi
    sleep 0.5
done

open "http://127.0.0.1:5000"
osascript -e 'display notification "Dashboard ready" with title "🌴 Palm Farm Management"'

wait $FLASK_PID
