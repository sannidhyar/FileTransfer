#!/bin/bash

# WiFi File Transfer Binary Builder Script
# This script creates a standalone executable from the Python application

# Exit on error (but with some handling)
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}      WiFi File Transfer - Binary Builder      ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo

# Get the absolute path of the application
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "Building from: $APP_DIR"

# Check if the source files exist
if [ ! -f "$APP_DIR/app.py" ]; then
    log_error "Cannot find app.py in $APP_DIR"
    log_error "Please run this script from the WiFi File Transfer directory"
    exit 1
fi

# Check dependencies
check_dependency() {
    local cmd=$1
    local install_cmd=$2
    
    if ! command -v "$cmd" &> /dev/null; then
        log_warning "$cmd is not installed."
        if [ -n "$install_cmd" ]; then
            log_info "Installing $cmd..."
            eval "$install_cmd" || {
                log_error "Failed to install $cmd. Please install it manually and try again."
                return 1
            }
            log_success "$cmd installed successfully!"
        else
            log_error "Please install $cmd and try again."
            return 1
        fi
    else
        log_info "Found $cmd: $(command -v "$cmd")"
    fi
    return 0
}

# Check for Python
check_dependency "python3" || exit 1

# Check for pip
check_dependency "pip3" "sudo apt-get update && sudo apt-get install -y python3-pip" || exit 1

# Install PyInstaller
log_info "Installing/upgrading PyInstaller..."
pip3 install --upgrade pyinstaller

# Install project dependencies
log_info "Installing project dependencies..."
if [ -f "$APP_DIR/requirements.txt" ]; then
    pip3 install -r "$APP_DIR/requirements.txt"
else
    log_warning "requirements.txt not found. Installing basic dependencies..."
    pip3 install flask flask-cors netifaces zeroconf
fi

# Create the build directory if it doesn't exist
BUILD_DIR="$APP_DIR/build"
if [ ! -d "$BUILD_DIR" ]; then
    mkdir -p "$BUILD_DIR"
fi

# Create the spec file
log_info "Creating PyInstaller spec file..."
SPEC_FILE="$APP_DIR/wifi_transfer.spec"

cat > "$SPEC_FILE" << EOL
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['app.py'],
             pathex=['$APP_DIR'],
             binaries=[],
             datas=[('static', 'static'), ('templates', 'templates')],
             hiddenimports=['flask', 'werkzeug', 'jinja2', 'flask_cors', 'netifaces', 'zeroconf'],
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
log_info "Building binary with PyInstaller..."
cd "$APP_DIR" && pyinstaller --clean --workpath="$BUILD_DIR" wifi_transfer.spec

# Check if build succeeded
if [ -f "$APP_DIR/dist/wifi-file-transfer" ]; then
    log_success "Build successful!"
    log_success "Standalone executable created at: $APP_DIR/dist/wifi-file-transfer"
    
    # Create a simple startup script for the binary
    STARTUP_SCRIPT="$APP_DIR/dist/start_wifi_transfer.sh"
    log_info "Creating startup script..."
    
    cat > "$STARTUP_SCRIPT" << EOL
#!/bin/bash
# Start WiFi File Transfer binary
DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"

# Default arguments
PORT=5000
CONFIG="\$DIR/config.json"
HOST="0.0.0.0"
DEBUG=0

# Parse command line arguments
while [[ \$# -gt 0 ]]; do
    case \$1 in
        --port=*)
            PORT="\${1#*=}"
            shift
            ;;
        --config=*)
            CONFIG="\${1#*=}"
            shift
            ;;
        --host=*)
            HOST="\${1#*=}"
            shift
            ;;
        --debug)
            DEBUG=1
            shift
            ;;
        *)
            echo "Unknown option: \$1"
            shift
            ;;
    esac
done

# Start the application
echo "Starting WiFi File Transfer..."
echo "Port: \$PORT"
echo "Config: \$CONFIG"
echo "Host: \$HOST"
[ \$DEBUG -eq 1 ] && echo "Debug mode: ON"

# Run the binary with the provided arguments
exec "\$DIR/wifi-file-transfer" --port=\$PORT --config=\$CONFIG --host=\$HOST \$([ \$DEBUG -eq 1 ] && echo "--debug")
EOL
    chmod +x "$STARTUP_SCRIPT"
    
    # Create installation script for the binary
    BINARY_INSTALL="$APP_DIR/dist/install_binary.sh"
    log_info "Creating installation script..."
    
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

# Log functions
log_info() {
    echo -e "\${BLUE}[INFO]\${NC} \$1"
}

log_success() {
    echo -e "\${GREEN}[SUCCESS]\${NC} \$1"
}

log_warning() {
    echo -e "\${YELLOW}[WARNING]\${NC} \$1"
}

log_error() {
    echo -e "\${RED}[ERROR]\${NC} \$1"
}

# Banner
echo
echo -e "\${BLUE}===============================================\${NC}"
echo -e "\${BLUE}  WiFi File Transfer Binary - Installation Script \${NC}"
echo -e "\${BLUE}===============================================\${NC}"
echo

# Check if running as root
if [ "\$EUID" -ne 0 ]; then
    log_error "Please run this script as root or with sudo"
    exit 1
fi

# Get the absolute path of the binary
BINARY_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
log_info "Installing from: \$BINARY_DIR"

# Check if the binary exists
if [ ! -f "\$BINARY_DIR/wifi-file-transfer" ]; then
    log_error "Cannot find wifi-file-transfer binary in \$BINARY_DIR"
    exit 1
fi

# Ensure the binary is executable
chmod +x "\$BINARY_DIR/wifi-file-transfer"

# Ensure config directory exists
CONFIG_FILE="\$BINARY_DIR/config.json"
log_info "Checking configuration file..."
if [ ! -f "\$CONFIG_FILE" ]; then
    log_warning "Configuration file not found. It will be created on first run."
fi

# Create data directory
DATA_DIR="\$BINARY_DIR/trans_store"
log_info "Creating data directory: \$DATA_DIR"
mkdir -p "\$DATA_DIR"
chmod 755 "\$DATA_DIR"

# Detect the current user
CURRENT_USER=\$(logname 2>/dev/null || echo "\$SUDO_USER")
if [ -z "\$CURRENT_USER" ]; then
    CURRENT_USER=\$(who am i | awk '{print \$1}')
fi

if [ -z "\$CURRENT_USER" ]; then
    log_warning "Could not determine the current user. Using 'root' as fallback."
    CURRENT_USER="root"
fi

CURRENT_GROUP=\$(id -gn "\$CURRENT_USER")
log_info "Service will run as user: \$CURRENT_USER"

# Set correct ownership
chown -R "\$CURRENT_USER:\$CURRENT_GROUP" "\$BINARY_DIR"

# Create a systemd service file
log_info "Creating systemd service..."
SERVICE_NAME="wifi-file-transfer"
SERVICE_PATH="/etc/systemd/system/\$SERVICE_NAME.service"

# Create the systemd service configuration
cat > "\$SERVICE_PATH" << EOLS
[Unit]
Description=WiFi File Transfer Service
After=network.target

[Service]
ExecStart=\$BINARY_DIR/wifi-file-transfer --config=\$CONFIG_FILE
WorkingDirectory=\$BINARY_DIR
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wifi-file-transfer
User=\$CURRENT_USER
Group=\$CURRENT_GROUP

[Install]
WantedBy=multi-user.target
EOLS

# Set permissions
chmod 644 "\$SERVICE_PATH"

# Enable and start the service
log_info "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable \$SERVICE_NAME
systemctl start \$SERVICE_NAME

# Wait a moment for the service to start
sleep 2

# Check service status
if systemctl is-active --quiet \$SERVICE_NAME; then
    log_success "Service is running successfully!"
else
    log_error "Service failed to start. Checking logs..."
    journalctl -u \$SERVICE_NAME --no-pager -n 20
    exit 1
fi

# Get IP address for display
IP_ADDRESS=\$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Display service status
echo
log_info "Service Status:"
systemctl status \$SERVICE_NAME --no-pager

# Print success message
echo
echo -e "\${GREEN}==============================================\${NC}"
echo -e "\${GREEN}WiFi File Transfer binary has been installed successfully\${NC}"
echo -e "\${GREEN}and will automatically start on system boot.\${NC}"
echo
if [ -n "\$IP_ADDRESS" ]; then
    echo -e "\${GREEN}You can access the application at:\${NC}"
    echo -e "\${BLUE}http://\$IP_ADDRESS:5000\${NC}"
fi
echo
echo -e "\${YELLOW}You can manage the service with these commands:\${NC}"
echo -e "  \${BLUE}sudo systemctl status \$SERVICE_NAME\${NC} - Check status"
echo -e "  \${BLUE}sudo systemctl stop \$SERVICE_NAME\${NC} - Stop the service"
echo -e "  \${BLUE}sudo systemctl start \$SERVICE_NAME\${NC} - Start the service"
echo -e "  \${BLUE}sudo systemctl restart \$SERVICE_NAME\${NC} - Restart the service"
echo -e "  \${BLUE}sudo systemctl disable \$SERVICE_NAME\${NC} - Disable autostart"
echo -e "  \${BLUE}journalctl -u \$SERVICE_NAME\${NC} - View logs"
echo -e "\${GREEN}==============================================\${NC}"
EOL
    chmod +x "$BINARY_INSTALL"
    
    # Create README for the binary distribution
    BINARY_README="$APP_DIR/dist/README.md"
    log_info "Creating documentation..."
    
    cat > "$BINARY_README" << EOL
# WiFi File Transfer - Binary Release

This is a standalone binary distribution of WiFi File Transfer. No Python installation is required.

## Installation

### As a Service (Recommended)

1. Make the installer script executable (if needed):
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

With custom settings:

\`\`\`
./start_wifi_transfer.sh --port=8080 --config=/path/to/your/config.json --host=0.0.0.0 --debug
\`\`\`

Or directly:

\`\`\`
./wifi-file-transfer --config=/path/to/your/config.json
\`\`\`

## Usage

After installation, the application will be available at:

- http://localhost:5000
- http://YOUR_IP_ADDRESS:5000 (accessible across your network)

## Configuration

The application uses a configuration file (default: \`config.json\`) to store settings:

- Service name
- Maximum file size
- Allowed file extensions
- Storage locations

The default configuration will be created automatically on first run if it doesn't exist.

## Troubleshooting

If you encounter any issues with the binary, check:

1. Permissions - ensure the binary is executable
2. Service logs - if running as a service, check \`journalctl -u wifi-file-transfer\`
3. Dependencies - the binary should include all dependencies, but system libraries may still be required

## Support

For more information and support, visit the GitHub repository.
EOL
    
    # Package everything
    log_info "Creating archive of the distribution..."
    DIST_DIR="$APP_DIR/dist"
    ARCHIVE_NAME="wifi-file-transfer-$(date +%Y%m%d).tar.gz"
    
    # Make sure the archive includes the README, install script, and start script
    cd "$DIST_DIR" && tar -czf "$ARCHIVE_NAME" wifi-file-transfer start_wifi_transfer.sh install_binary.sh README.md
    
    log_success "Archive created: $DIST_DIR/$ARCHIVE_NAME"
    
    echo
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}Binary distribution package created in the 'dist' folder${NC}"
    echo -e "${GREEN}This package can be distributed to other Linux systems${NC}"
    echo -e "${GREEN}with similar architecture without requiring Python.${NC}"
    echo
    echo -e "${YELLOW}To install on other systems:${NC}"
    echo -e "1. Copy the entire 'dist' directory to the target system or use the archive:"
    echo -e "   ${BLUE}$ARCHIVE_NAME${NC}"
    echo -e "2. Run ${BLUE}sudo ./install_binary.sh${NC} on the target system"
    echo -e "${GREEN}======================================================${NC}"
else
    log_error "Build failed. Check for errors in the PyInstaller output."
    exit 1
fi 