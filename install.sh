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
echo -e "${BLUE}     WiFi File Transfer - Installation Script   ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run this script as root or with sudo"
    exit 1
fi

# Get the absolute path of the application
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "Installing from: $APP_DIR"

# Check if required files exist
if [ ! -f "$APP_DIR/app.py" ]; then
    log_error "Cannot find app.py in $APP_DIR"
    log_error "Please run this script from the WiFi File Transfer directory"
    exit 1
fi

if [ ! -f "$APP_DIR/requirements.txt" ]; then
    log_warning "Cannot find requirements.txt in $APP_DIR"
    log_warning "Dependencies may not be installed correctly"
fi

# Get the actual (non-root) user
get_actual_user() {
    local user
    
    # Try logname first
    user=$(logname 2>/dev/null) || user=""
    
    # If that failed, try who am i
    if [ -z "$user" ]; then
        user=$(who am i | awk '{print $1}' 2>/dev/null) || user=""
    fi
    
    # Last resort: try to get it from SUDO_USER
    if [ -z "$user" ]; then
        user=$SUDO_USER
    fi
    
    echo "$user"
}

ACTUAL_USER=$(get_actual_user)

if [ -z "$ACTUAL_USER" ]; then
    log_error "Could not determine the actual user. Please run with 'sudo' instead of 'su'."
    exit 1
fi

log_info "Detected user: $ACTUAL_USER"

# Find conda in common locations
find_conda() {
    local conda_locations=(
        "/home/$ACTUAL_USER/anaconda3/bin/conda"
        "/home/$ACTUAL_USER/miniconda3/bin/conda"
        "/opt/anaconda3/bin/conda"
        "/opt/miniconda3/bin/conda"
        "/usr/local/anaconda3/bin/conda"
        "/usr/local/miniconda3/bin/conda"
    )
    
    local conda_path=""
    
    # Check common locations
    for loc in "${conda_locations[@]}"; do
        if [ -f "$loc" ]; then
            conda_path="$loc"
            break
        fi
    done
    
    # If not found, try in user's PATH
    if [ -z "$conda_path" ]; then
        local user_path
        user_path=$(sudo -u "$ACTUAL_USER" bash -c 'echo $PATH')
        
        # Split the PATH and look for conda
        IFS=':' read -ra path_dirs <<< "$user_path"
        for dir in "${path_dirs[@]}"; do
            if [ -f "$dir/conda" ]; then
                conda_path="$dir/conda"
                break
            fi
        done
    fi
    
    echo "$conda_path"
}

CONDA_PATH=$(find_conda)

if [ -z "$CONDA_PATH" ]; then
    log_error "Could not find conda installation. Please make sure conda is installed."
    log_warning "If conda is installed in a non-standard location, please modify this script."
    exit 1
fi

log_info "Found conda at: $CONDA_PATH"

# Run conda commands as the actual user
CONDA_ROOT=$(dirname $(dirname "$CONDA_PATH"))
log_info "Checking for wifitransfer conda environment..."

# Check if the environment exists
ENV_EXISTS=$(sudo -u "$ACTUAL_USER" bash -c "$CONDA_PATH env list" | grep "wifitransfer")

if [ -z "$ENV_EXISTS" ]; then
    log_error "Error: 'wifitransfer' conda environment not found."
    log_info "Creating the environment for you..."
    
    # Create the environment
    log_info "Creating conda environment 'wifitransfer'..."
    sudo -u "$ACTUAL_USER" bash -c "$CONDA_PATH create -n wifitransfer python=3.9 -y"
    
    if [ $? -ne 0 ]; then
        log_error "Failed to create conda environment."
        log_info "Please create the environment manually with:"
        echo -e "conda create -n wifitransfer python=3.9"
        echo -e "conda activate wifitransfer"
        echo -e "pip install -r $APP_DIR/requirements.txt"
        exit 1
    fi
    
    # Install dependencies
    log_info "Installing dependencies from requirements.txt..."
    sudo -u "$ACTUAL_USER" bash -c "$CONDA_PATH run -n wifitransfer pip install -r $APP_DIR/requirements.txt"
    
    if [ $? -ne 0 ]; then
        log_error "Failed to install dependencies."
        log_warning "You may need to install them manually with:"
        echo -e "conda activate wifitransfer"
        echo -e "pip install -r $APP_DIR/requirements.txt"
    fi
fi

# Get the path to the conda environment
CONDA_ENV_PATH="$CONDA_ROOT/envs/wifitransfer"
CONDA_PYTHON_PATH="$CONDA_ENV_PATH/bin/python"

if [ ! -f "$CONDA_PYTHON_PATH" ]; then
    log_error "Could not find Python in the wifitransfer environment."
    exit 1
fi

log_info "Using Python from wifitransfer conda environment: $CONDA_PYTHON_PATH"

# Create a systemd service file
log_info "Creating systemd service..."
SERVICE_NAME="wifi-file-transfer"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME.service"

# Get the current user for the service
CURRENT_USER=$ACTUAL_USER
CURRENT_GROUP=$(id -gn "$CURRENT_USER")

# Check if config.json exists and create the config directory if needed
CONFIG_DIR="$APP_DIR"
CONFIG_FILE="$CONFIG_DIR/config.json"

log_info "Ensuring configuration directory exists..."
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
    chown "$CURRENT_USER:$CURRENT_GROUP" "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"
fi

# Create the data directory
DATA_DIR="$APP_DIR/trans_store"
log_info "Ensuring data directory exists: $DATA_DIR"
mkdir -p "$DATA_DIR"
chown "$CURRENT_USER:$CURRENT_GROUP" "$DATA_DIR"
chmod 755 "$DATA_DIR"

# Create the systemd service configuration with conda environment
cat > "$SERVICE_PATH" << EOL
[Unit]
Description=WiFi File Transfer Service
After=network.target

[Service]
ExecStart=$CONDA_PYTHON_PATH $APP_DIR/app.py --config=$CONFIG_FILE
WorkingDirectory=$APP_DIR
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
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
log_info "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Wait a moment for the service to start
sleep 2

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    log_success "Service is running successfully!"
else
    log_error "Service failed to start. Checking logs..."
    journalctl -u $SERVICE_NAME --no-pager -n 20
    exit 1
fi

# Get the IP address
IP_ADDRESS=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Display service status
echo
log_info "Service Status:"
systemctl status $SERVICE_NAME --no-pager

# Print success message
echo
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}WiFi File Transfer has been installed successfully${NC}"
echo -e "${GREEN}using the 'wifitransfer' conda environment${NC}"
echo -e "${GREEN}and will automatically start on system boot.${NC}"
echo
if [ -n "$IP_ADDRESS" ]; then
    echo -e "${GREEN}You can access the application at:${NC}"
    echo -e "${BLUE}http://$IP_ADDRESS:5000${NC}"
fi
echo
echo -e "${YELLOW}You can manage the service with these commands:${NC}"
echo -e "  ${BLUE}sudo systemctl status $SERVICE_NAME${NC} - Check status"
echo -e "  ${BLUE}sudo systemctl stop $SERVICE_NAME${NC} - Stop the service"
echo -e "  ${BLUE}sudo systemctl start $SERVICE_NAME${NC} - Start the service"
echo -e "  ${BLUE}sudo systemctl restart $SERVICE_NAME${NC} - Restart the service"
echo -e "  ${BLUE}sudo systemctl disable $SERVICE_NAME${NC} - Disable autostart"
echo -e "  ${BLUE}journalctl -u $SERVICE_NAME${NC} - View logs"
echo -e "${GREEN}==============================================${NC}" 