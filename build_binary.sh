#!/bin/bash

# WiFi File Transfer Binary Builder Script
# This script creates a standalone executable from the Python application

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== WiFi File Transfer - Binary Builder =====${NC}"
echo

# Get the absolute path of the application
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}Building from:${NC} $APP_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3 and try again.${NC}"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}pip3 is not installed. Installing pip...${NC}"
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi

# Install PyInstaller
echo -e "${BLUE}Installing PyInstaller...${NC}"
pip3 install pyinstaller

# Install project dependencies
echo -e "${BLUE}Installing project dependencies...${NC}"
pip3 install -r "$APP_DIR/requirements.txt"

# Create the spec file
echo -e "${BLUE}Creating PyInstaller spec file...${NC}"
cat > "$APP_DIR/wifi_transfer.spec" << EOL
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['app.py'],
             pathex=['$APP_DIR'],
             binaries=[],
             datas=[('static', 'static'), ('templates', 'templates')],
             hiddenimports=['flask', 'werkzeug', 'jinja2'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='wifi-file-transfer',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True)
EOL

# Build the binary
echo -e "${BLUE}Building binary with PyInstaller...${NC}"
cd "$APP_DIR" && pyinstaller --clean wifi_transfer.spec

# Check if build succeeded
if [ -f "$APP_DIR/dist/wifi-file-transfer" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    echo -e "${GREEN}Standalone executable created at:${NC} $APP_DIR/dist/wifi-file-transfer"
    
    # Create a simple startup script for the binary
    STARTUP_SCRIPT="$APP_DIR/dist/start_wifi_transfer.sh"
    cat > "$STARTUP_SCRIPT" << EOL
#!/bin/bash
# Start WiFi File Transfer binary
DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
"\$DIR/wifi-file-transfer" "\$@"
EOL
    chmod +x "$STARTUP_SCRIPT"
    
    # Create installation script for the binary
    BINARY_INSTALL="$APP_DIR/dist/install_binary.sh"
    cat > "$BINARY_INSTALL" << EOL
#!/bin/bash

# WiFi File Transfer Binary Installation Script
# This script installs the WiFi File Transfer binary as a systemd service

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "\${BLUE}===== WiFi File Transfer Binary - Installation Script =====${NC}"
echo

# Check if running as root
if [ "\$EUID" -ne 0 ]; then
  echo -e "\${RED}Please run this script as root or with sudo{NC}"
  exit 1
fi

# Get the absolute path of the binary
BINARY_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
echo -e "\${GREEN}Installing from:${NC} \$BINARY_DIR"

# Create a systemd service file
echo -e "\${BLUE}Creating systemd service...${NC}"
SERVICE_NAME="wifi-file-transfer"
SERVICE_PATH="/etc/systemd/system/\$SERVICE_NAME.service"

# Create the systemd service configuration
cat > "\$SERVICE_PATH" << EOLS
[Unit]
Description=WiFi File Transfer Service
After=network.target

[Service]
ExecStart=\$BINARY_DIR/wifi-file-transfer
WorkingDirectory=\$BINARY_DIR
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=wifi-file-transfer
User=\$(logname)
Group=\$(logname)

[Install]
WantedBy=multi-user.target
EOLS

# Set permissions
chmod 644 "\$SERVICE_PATH"

# Enable and start the service
echo -e "\${BLUE}Enabling and starting the service...${NC}"
systemctl daemon-reload
systemctl enable \$SERVICE_NAME
systemctl start \$SERVICE_NAME

# Check service status
if systemctl is-active --quiet \$SERVICE_NAME; then
    echo -e "\${GREEN}Service is running successfully!${NC}"
else
    echo -e "\${RED}Service failed to start. Check logs with 'journalctl -u \$SERVICE_NAME'${NC}"
    exit 1
fi

# Display service status
echo
echo -e "\${BLUE}Service Status:${NC}"
systemctl status \$SERVICE_NAME --no-pager

# Print success message
echo
echo -e "\${GREEN}==============================================${NC}"
echo -e "\${GREEN}WiFi File Transfer binary has been installed successfully${NC}"
echo -e "\${GREEN}and will automatically start on system boot.${NC}"
echo
echo -e "\${YELLOW}You can manage the service with these commands:${NC}"
echo -e "  \${BLUE}sudo systemctl status \$SERVICE_NAME${NC} - Check status"
echo -e "  \${BLUE}sudo systemctl stop \$SERVICE_NAME${NC} - Stop the service"
echo -e "  \${BLUE}sudo systemctl start \$SERVICE_NAME${NC} - Start the service"
echo -e "  \${BLUE}sudo systemctl restart \$SERVICE_NAME${NC} - Restart the service"
echo -e "  \${BLUE}sudo systemctl disable \$SERVICE_NAME${NC} - Disable autostart"
echo -e "\${GREEN}==============================================${NC}"
EOL
    chmod +x "$BINARY_INSTALL"
    
    # Create README for the binary distribution
    BINARY_README="$APP_DIR/dist/README.md"
    cat > "$BINARY_README" << EOL
# WiFi File Transfer - Binary Release

This is a standalone binary distribution of WiFi File Transfer. No Python installation is required.

## Installation

### As a Service (Recommended)

1. Make the installer script executable:
   \`\`\`
   chmod +x install_binary.sh
   \`\`\`

2. Run the installer with sudo:
   \`\`\`
   sudo ./install_binary.sh
   \`\`\`

### Manual Execution

To run the application directly:

\`\`\`
./start_wifi_transfer.sh
\`\`\`

## Usage

After installation, the application will be available at:

- http://localhost:5000
- http://YOUR_IP_ADDRESS:5000 (accessible across your network)

## Troubleshooting

If you encounter any issues with the binary, check:

1. Permissions - ensure the binary is executable
2. Service logs - if running as a service, check \`journalctl -u wifi-file-transfer\`
3. Dependencies - the binary should include all dependencies, but system libraries may still be required
EOL
    
    echo
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}Binary distribution package created in the 'dist' folder${NC}"
    echo -e "${GREEN}This package can be distributed to other Linux systems${NC}"
    echo -e "${GREEN}with similar architecture without requiring Python.${NC}"
    echo
    echo -e "${YELLOW}To install on other systems:${NC}"
    echo -e "1. Copy the entire 'dist' directory to the target system"
    echo -e "2. Run ${BLUE}sudo ./install_binary.sh${NC} on the target system"
    echo -e "${GREEN}======================================================${NC}"
else
    echo -e "${RED}Build failed. Check for errors in the PyInstaller output.${NC}"
    exit 1
fi 