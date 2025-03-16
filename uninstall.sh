#!/bin/bash

# WiFi File Transfer Uninstallation Script
# This script removes the WiFi File Transfer service
# from system startup

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== WiFi File Transfer - Uninstallation Script =====${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run this script as root or with sudo${NC}"
  exit 1
fi

SERVICE_NAME="wifi-file-transfer"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME.service"

# Check if service file exists
if [ ! -f "$SERVICE_PATH" ]; then
    echo -e "${YELLOW}Service file not found. WiFi File Transfer may not have been installed as a service.${NC}"
else
    # Stop and disable the service
    echo -e "${BLUE}Stopping and disabling the service...${NC}"
    systemctl stop $SERVICE_NAME || true
    systemctl disable $SERVICE_NAME || true
    
    # Remove the service file
    echo -e "${BLUE}Removing service file...${NC}"
    rm -f "$SERVICE_PATH"
    
    # Reload systemd
    echo -e "${BLUE}Reloading systemd...${NC}"
    systemctl daemon-reload
    systemctl reset-failed
    
    echo -e "${GREEN}Service successfully removed!${NC}"
fi

# Ask if the user wants to remove any data files
echo
echo -e "${YELLOW}Do you want to remove all uploaded files and data? (y/N)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo -e "${BLUE}Removing uploaded files...${NC}"
    
    # Find and remove files
    if [ -d "$APP_DIR/uploads" ]; then
        rm -rf "$APP_DIR/uploads"
        echo -e "${GREEN}Uploads directory removed.${NC}"
    fi
    
    if [ -d "$APP_DIR/files" ]; then
        rm -rf "$APP_DIR/files"
        echo -e "${GREEN}Files directory removed.${NC}"
    fi
    
    if [ -d "$APP_DIR/downloads" ]; then
        rm -rf "$APP_DIR/downloads"
        echo -e "${GREEN}Downloads directory removed.${NC}"
    fi
    
    # Remove any database files
    rm -f "$APP_DIR"/*.db "$APP_DIR"/*.sqlite "$APP_DIR"/*.sqlite3
    
    echo -e "${GREEN}All data files have been removed.${NC}"
else
    echo -e "${GREEN}Data files were not removed. You can delete them manually if needed.${NC}"
fi

echo
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}WiFi File Transfer has been uninstalled.${NC}"
echo -e "${GREEN}==============================================${NC}" 