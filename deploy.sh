#!/bin/bash

# HydePark Sync - Automated Deployment Script
# This script automates the complete setup and deployment of the sync service

set -e  # Exit on any error

# Configuration
APP_NAME="hydepark-sync"
APP_DIR="/opt/$APP_NAME"
SERVICE_NAME="$APP_NAME.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER=$(whoami)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   HydePark Sync - Auto Deployment     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

print_error() {
    echo -e "${RED}❌${NC} ERROR: $1"
    exit 1
}

# Quick update function - only copy changed files
quick_update() {
    print_header
    print_step "Quick update mode - copying application files..."
    
    # Stop service
    sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
    
    # Copy updated files
    sudo cp -r "$REPO_DIR"/*.py "$APP_DIR/" 2>/dev/null || true
    sudo cp -r "$REPO_DIR"/api "$APP_DIR/" 2>/dev/null || true
    sudo cp -r "$REPO_DIR"/processors "$APP_DIR/" 2>/dev/null || true
    sudo cp -r "$REPO_DIR"/dashboard "$APP_DIR/" 2>/dev/null || true
    sudo cp -r "$REPO_DIR"/utils "$APP_DIR/" 2>/dev/null || true
    sudo chown -R $USER:$USER "$APP_DIR"
    
    # Restart service
    sudo systemctl start $SERVICE_NAME
    
    print_success "Quick update completed!"
    print_step "Checking service status..."
    sudo systemctl status $SERVICE_NAME --no-pager -l
    
    exit 0
}

# Check if --quick flag is passed
if [ "$1" == "--quick" ] || [ "$1" == "-q" ]; then
    quick_update
fi

# ============================================
# PRE-FLIGHT CHECKS
# ============================================

print_header
print_step "Running pre-flight checks..."

# Check Ubuntu/Debian
if ! command -v apt-get &> /dev/null; then
    print_error "This script requires Ubuntu/Debian (apt-get not found)"
fi

# Check internet connection (for package installation)
if ! ping -c 1 8.8.8.8 &> /dev/null; then
    print_warning "No internet connection detected. Installation may fail without internet."
fi

print_success "Pre-flight checks passed"

# ============================================
# CLEANUP OLD INSTALLATIONS
# ============================================

print_step "Cleaning up any old installations..."

# Stop and disable old service
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    sudo systemctl stop $SERVICE_NAME
    print_success "Stopped old service"
fi

if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    sudo systemctl disable $SERVICE_NAME
    print_success "Disabled old service"
fi

# Kill any process on port 8080
if sudo lsof -ti:$DASHBOARD_PORT &> /dev/null; then
    print_warning "Port $DASHBOARD_PORT is in use, killing process..."
    sudo kill -9 $(sudo lsof -ti:$DASHBOARD_PORT) 2>/dev/null || true
    sleep 2
    print_success "Port $DASHBOARD_PORT freed"
fi

# Remove old installation
if [ -d "$APP_DIR" ]; then
    print_warning "Removing old installation..."
    sudo rm -rf $APP_DIR
fi

# Remove old service file
if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
    sudo rm -f /etc/systemd/system/$SERVICE_NAME
    sudo systemctl daemon-reload
fi

print_success "Cleanup complete"

# ============================================
# SYSTEM DEPENDENCIES
# ============================================

print_step "Installing system dependencies (this may take a few minutes)..."

# Update package list
echo "   Updating package lists..."
sudo apt-get update -qq || {
    print_error "Failed to update package lists. Check your internet connection."
}

# Install all required system packages
echo "   Installing packages (this may take 2-5 minutes)..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    cmake \
    build-essential \
    pkg-config \
    libssl-dev \
    libffi-dev \
    libopenblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    gfortran \
    libhdf5-dev \
    libqhull-dev \
    libboost-all-dev \
    lsof \
    net-tools \
    curl \
    wget || {
    print_error "Failed to install system packages. Check the output above."
}

print_success "System dependencies installed"

# ============================================
# FIREWALL CONFIGURATION
# ============================================

print_step "Configuring firewall..."

# Check if UFW is installed and active
if command -v ufw &> /dev/null; then
    if sudo ufw status | grep -q "Status: active"; then
        print_warning "UFW is active, opening port $DASHBOARD_PORT..."
        sudo ufw allow $DASHBOARD_PORT/tcp > /dev/null 2>&1
        print_success "Port $DASHBOARD_PORT allowed in UFW"
    else
        print_success "UFW is installed but not active"
    fi
fi

# Check if firewalld is installed and active
if command -v firewall-cmd &> /dev/null; then
    if sudo firewall-cmd --state 2>/dev/null | grep -q "running"; then
        print_warning "firewalld is active, opening port $DASHBOARD_PORT..."
        sudo firewall-cmd --add-port=$DASHBOARD_PORT/tcp --permanent > /dev/null 2>&1
        sudo firewall-cmd --reload > /dev/null 2>&1
        print_success "Port $DASHBOARD_PORT allowed in firewalld"
    else
        print_success "firewalld is installed but not running"
    fi
fi

print_success "Firewall configured"

# ============================================
# APPLICATION INSTALLATION
# ============================================

print_step "Creating application directory..."

sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR
print_success "Application directory created: $APP_DIR"

print_step "Copying application files..."

# Copy all necessary files
cp -r api $APP_DIR/
cp -r processors $APP_DIR/
cp -r dashboard $APP_DIR/
cp -r utils $APP_DIR/
cp -r systemd $APP_DIR/
cp main.py $APP_DIR/
cp config.py $APP_DIR/
cp database.py $APP_DIR/
cp requirements.txt $APP_DIR/
cp post_deploy_check.sh $APP_DIR/ 2>/dev/null || true

print_success "Application files copied"

# ============================================
# PYTHON VIRTUAL ENVIRONMENT
# ============================================

print_step "Setting up Python virtual environment..."

cd $APP_DIR
python3 -m venv venv
source venv/bin/activate

print_step "Installing Python packages (this will take 5-10 minutes)..."

# Upgrade pip and wheel first
pip install --upgrade pip wheel -q
# Pin setuptools to avoid pkg_resources deprecation issues
pip install 'setuptools<81' -q

# Install numpy first (required for other packages)
echo "   [1/5] Installing numpy..."
pip install numpy==1.26.2 -q

# Install cmake (build dependency)
echo "   [2/5] Installing cmake..."
pip install cmake -q

# Install dlib (this is the slow one)
echo "   [3/5] Installing dlib (this takes time)..."
pip install dlib -q || {
    print_warning "dlib installation from pip failed, trying compilation..."
    pip install dlib --no-cache-dir
}

# Install face_recognition
echo "   [4/5] Installing face_recognition..."
pip install face-recognition -q

# Install face_recognition_models - try PyPI first, then GitHub
echo "   [5/5] Installing face recognition models (this may take 1-2 minutes)..."
echo "        Please wait, downloading models..."

# Try PyPI first (faster)
if pip install face-recognition-models --no-cache-dir 2>&1 | grep -q "Successfully installed"; then
    print_success "Models installed from PyPI"
else
    echo "        PyPI failed, trying GitHub repository..."
    if pip install git+https://github.com/ageitgey/face_recognition_models 2>&1 | grep -q "Successfully installed"; then
        print_success "Models installed from GitHub"
    else
        # Last resort: try without git
        echo "        GitHub failed, trying direct download..."
        pip install https://github.com/ageitgey/face_recognition_models/archive/master.zip || {
            print_warning "Could not install face_recognition_models automatically."
            print_warning "The system will work but face detection may be limited."
            print_warning "You can install it later with: pip install face-recognition-models"
        }
    fi
fi

# Install OpenCV (headless) explicitly for servers
echo "   Installing OpenCV (headless)..."
pip install opencv-python-headless==4.8.1.78 -q

# Install remaining dependencies
echo "   Installing remaining packages..."
pip install -r requirements.txt -q || {
    print_error "Failed to install Python requirements."
}

# Verify critical imports
echo "   Verifying installation..."
python3 -c "
import face_recognition
import face_recognition_models
import numpy
import cv2
print('   ✓ All critical packages verified')
" || {
    print_error "Package verification failed. Some dependencies are missing."
}

print_success "Python environment ready"

# ============================================
# DATA DIRECTORIES
# ============================================

print_step "Creating data directories..."

mkdir -p $APP_DIR/data/faces
mkdir -p $APP_DIR/data/id_cards

# Create empty JSON files
echo "[]" > $APP_DIR/data/workers.json
echo "[]" > $APP_DIR/data/request_logs.json

# Set proper permissions
chmod 755 $APP_DIR/data
chmod 755 $APP_DIR/data/faces
chmod 755 $APP_DIR/data/id_cards
chmod 644 $APP_DIR/data/workers.json
chmod 644 $APP_DIR/data/request_logs.json

print_success "Data directories created"

# ============================================
# SYSTEMD SERVICE
# ============================================

print_step "Installing systemd service..."

# Replace user placeholder and install service
sed "s/%i/$USER/g" $APP_DIR/systemd/$SERVICE_NAME | \
    sudo tee /etc/systemd/system/$SERVICE_NAME > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME > /dev/null 2>&1

print_success "Service installed and enabled"

# ============================================
# START SERVICE
# ============================================

print_step "Starting service..."

sudo systemctl start $SERVICE_NAME

# Wait for service to start
sleep 3

# Check if service is running
if ! systemctl is-active --quiet $SERVICE_NAME; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ❌ Service Failed to Start ❌        ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "Last 30 lines of logs:"
    echo ""
    sudo journalctl -u $SERVICE_NAME -n 30 --no-pager
    echo ""
    print_error "Service failed to start! See logs above for details."
fi

print_success "Service started"

# ============================================
# HEALTH CHECK
# ============================================

print_step "Running health checks..."

# Give service time to initialize
sleep 5

# Check if port is listening
MAX_RETRIES=15
RETRY_COUNT=0
PORT_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if sudo lsof -i:$DASHBOARD_PORT | grep LISTEN &> /dev/null; then
        PORT_READY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done

if [ "$PORT_READY" = false ]; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ❌ Dashboard Not Responding ❌       ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "Service logs:"
    echo ""
    sudo journalctl -u $SERVICE_NAME -n 30 --no-pager
    echo ""
    print_error "Dashboard port $DASHBOARD_PORT is not responding!"
fi

print_success "Port $DASHBOARD_PORT is listening"

# Try HTTP connection
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$DASHBOARD_PORT 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        print_success "Dashboard is responding (HTTP $HTTP_CODE)"
    else
        print_warning "Dashboard port is open but HTTP not ready yet (may still be initializing)"
    fi
fi

# ============================================
# FINAL REPORT
# ============================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     🎉 Deployment Successful! 🎉       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Get IP addresses
echo -e "${BLUE}📡 Access Dashboard:${NC}"
if command -v hostname &> /dev/null; then
    HOSTNAME=$(hostname -I | awk '{print $1}')
    if [ -n "$HOSTNAME" ]; then
        echo "   🌐 http://$HOSTNAME:$DASHBOARD_PORT"
    fi
fi
echo "   🌐 http://localhost:$DASHBOARD_PORT"
echo ""

echo -e "${BLUE}🔐 Login Credentials:${NC}"
echo "   Username: admin"
echo "   Password: 123456"
echo ""

echo -e "${BLUE}📊 Service Status:${NC}"
sudo systemctl status $SERVICE_NAME --no-pager | head -n 5
echo ""

echo -e "${BLUE}📝 Useful Commands:${NC}"
echo "   View logs:      sudo journalctl -u $SERVICE_NAME -f"
echo "   Stop service:   sudo systemctl stop $SERVICE_NAME"
echo "   Start service:  sudo systemctl start $SERVICE_NAME"
echo "   Restart:        sudo systemctl restart $SERVICE_NAME"
echo "   Status:         sudo systemctl status $SERVICE_NAME"
echo ""

echo -e "${BLUE}📂 Application Files:${NC}"
echo "   Directory:      $APP_DIR"
echo "   Config:         $APP_DIR/config.py"
echo "   Data:           $APP_DIR/data/"
echo ""

echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "   • Edit config.py to update Supabase/HikCentral settings"
echo "   • Restart service after config changes"
echo "   • Dashboard runs on port $DASHBOARD_PORT"
echo "   • All data stored in $APP_DIR/data/"
echo ""

print_success "System is ready to use!"
echo ""