#!/bin/bash

# WiFi File Transfer Installation Script
# This script installs the WiFi File Transfer application
# to run on system startup via systemd using a Conda environment

# Exit on error
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== WiFi File Transfer - Installation Script =====${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run this script as root or with sudo${NC}"
  exit 1
fi

# Get the absolute path of the application
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}Installing from:${NC} $APP_DIR"

# Get the actual (non-root) user
ACTUAL_USER=$(logname || who am i | awk '{print $1}')
if [ -z "$ACTUAL_USER" ]; then
    # Last resort: try to get it from SUDO_USER
    ACTUAL_USER=$SUDO_USER
fi

if [ -z "$ACTUAL_USER" ]; then
    echo -e "${RED}Could not determine the actual user. Please run with 'sudo' instead of 'su'.${NC}"
    exit 1
fi

echo -e "${GREEN}Detected user:${NC} $ACTUAL_USER"

# Find conda in common locations
CONDA_LOCATIONS=(
    "/home/$ACTUAL_USER/anaconda3/bin/conda"
    "/home/$ACTUAL_USER/miniconda3/bin/conda"
    "/opt/anaconda3/bin/conda"
    "/opt/miniconda3/bin/conda"
    "/usr/local/anaconda3/bin/conda"
    "/usr/local/miniconda3/bin/conda"
)

CONDA_PATH=""
for loc in "${CONDA_LOCATIONS[@]}"; do
    if [ -f "$loc" ]; then
        CONDA_PATH="$loc"
        break
    fi
done

# If not found in common locations, try to find it in user's PATH
if [ -z "$CONDA_PATH" ]; then
    # Get the user's PATH
    USER_PATH=$(sudo -u "$ACTUAL_USER" bash -c 'echo $PATH')
    
    # Split the PATH and look for conda
    IFS=':' read -ra PATH_DIRS <<< "$USER_PATH"
    for dir in "${PATH_DIRS[@]}"; do
        if [ -f "$dir/conda" ]; then
            CONDA_PATH="$dir/conda"
            break
        fi
    done
fi

if [ -z "$CONDA_PATH" ]; then
    echo -e "${RED}Could not find conda installation. Please make sure conda is installed.${NC}"
    echo -e "${YELLOW}If conda is installed in a non-standard location, please modify this script.${NC}"
    exit 1
fi

echo -e "${GREEN}Found conda at:${NC} $CONDA_PATH"

# Run conda commands as the actual user
CONDA_ROOT=$(dirname $(dirname "$CONDA_PATH"))
echo -e "${BLUE}Checking for wifitransfer conda environment...${NC}"

# Check if the environment exists
ENV_EXISTS=$(sudo -u "$ACTUAL_USER" bash -c "$CONDA_PATH env list" | grep "wifitransfer")

if [ -z "$ENV_EXISTS" ]; then
    echo -e "${RED}Error: 'wifitransfer' conda environment not found.${NC}"
    echo -e "${YELLOW}Please create the environment first with:${NC}"
    echo -e "conda create -n wifitransfer python=3.9 flask"
    echo -e "conda activate wifitransfer"
    echo -e "pip install -r $APP_DIR/requirements.txt"
    exit 1
fi

# Get the path to the conda environment
CONDA_ENV_PATH="$CONDA_ROOT/envs/wifitransfer"
CONDA_PYTHON_PATH="$CONDA_ENV_PATH/bin/python"

if [ ! -f "$CONDA_PYTHON_PATH" ]; then
    echo -e "${RED}Could not find Python in the wifitransfer environment.${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python from wifitransfer conda environment:${NC} $CONDA_PYTHON_PATH"

# Create a systemd service file
echo -e "${BLUE}Creating systemd service...${NC}"
SERVICE_NAME="wifi-file-transfer"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME.service"

# Get the current user for the service
CURRENT_USER=$ACTUAL_USER
CURRENT_GROUP=$(id -gn "$CURRENT_USER")

# Create the systemd service configuration with conda environment
cat > "$SERVICE_PATH" << EOL
[Unit]
Description=WiFi File Transfer Service
After=network.target

[Service]
ExecStart=$CONDA_PYTHON_PATH $APP_DIR/app.py
WorkingDirectory=$APP_DIR
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=wifi-file-transfer
User=$CURRENT_USER
Group=$CURRENT_GROUP
Environment="PATH=$CONDA_ENV_PATH/bin:$PATH"

[Install]
WantedBy=multi-user.target
EOL

# Set permissions
chmod 644 "$SERVICE_PATH"

# Enable and start the service
echo -e "${BLUE}Enabling and starting the service...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}Service is running successfully!${NC}"
else
    echo -e "${RED}Service failed to start. Check logs with 'journalctl -u $SERVICE_NAME'${NC}"
    exit 1
fi

# Display service status
echo
echo -e "${BLUE}Service Status:${NC}"
systemctl status $SERVICE_NAME --no-pager

# Print success message
echo
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}WiFi File Transfer has been installed successfully${NC}"
echo -e "${GREEN}using the 'wifitransfer' conda environment${NC}"
echo -e "${GREEN}and will automatically start on system boot.${NC}"
echo
echo -e "${YELLOW}You can manage the service with these commands:${NC}"
echo -e "  ${BLUE}sudo systemctl status $SERVICE_NAME${NC} - Check status"
echo -e "  ${BLUE}sudo systemctl stop $SERVICE_NAME${NC} - Stop the service"
echo -e "  ${BLUE}sudo systemctl start $SERVICE_NAME${NC} - Start the service"
echo -e "  ${BLUE}sudo systemctl restart $SERVICE_NAME${NC} - Restart the service"
echo -e "  ${BLUE}sudo systemctl disable $SERVICE_NAME${NC} - Disable autostart"
echo -e "${GREEN}==============================================${NC}" 