#!/bin/bash

# Post-deployment verification script
# Automatically run by deploy.sh or can be run manually

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_NAME="hydepark-sync"
APP_DIR="/opt/hydepark-sync"
DASHBOARD_PORT=8080

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Post-Deployment Health Check        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

ERRORS=0

# Check 1: Service Status
echo -n "Checking service status... "
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: Port Listening
echo -n "Checking port $DASHBOARD_PORT... "
if sudo lsof -i:$DASHBOARD_PORT | grep LISTEN &> /dev/null; then
    echo -e "${GREEN}✓ Listening${NC}"
else
    echo -e "${RED}✗ Not listening${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Python Process
echo -n "Checking Python process... "
if pgrep -f "python.*main.py" > /dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: Data Directory
echo -n "Checking data directory... "
if [ -d "$APP_DIR/data" ] && [ -f "$APP_DIR/data/workers.json" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Config File
echo -n "Checking configuration... "
if [ -f "$APP_DIR/config.py" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 6: Virtual Environment
echo -n "Checking Python venv... "
if [ -d "$APP_DIR/venv" ] && [ -f "$APP_DIR/venv/bin/python" ]; then
    echo -e "${GREEN}✓ Configured${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 7: HTTP Response
echo -n "Testing HTTP response... "
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$DASHBOARD_PORT || echo "000")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        echo -e "${GREEN}✓ Responding (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}✗ Not responding (HTTP $HTTP_CODE)${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⊘ curl not installed, skipping${NC}"
fi

echo ""

# Final result
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      ✅ All Checks Passed! ✅          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "System is healthy and ready to use!"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║      ❌ $ERRORS Check(s) Failed! ❌          ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "Troubleshooting:"
    echo ""
    echo "1. View service logs:"
    echo "   sudo journalctl -u $SERVICE_NAME -n 100"
    echo ""
    echo "2. Check service status:"
    echo "   sudo systemctl status $SERVICE_NAME"
    echo ""
    echo "3. Try manual run to see errors:"
    echo "   cd $APP_DIR"
    echo "   source venv/bin/activate"
    echo "   python main.py"
    echo ""
    exit 1
fi
