# WiFi File Transfer

A web-based file sharing application that allows you to easily transfer files across your local network.

## Features

- Simple web interface for uploading and downloading files
- Automatic startup as a system service
- Dark/light theme support
- Mobile-friendly design
- File management (upload, download, delete)
- Storage usage monitoring

## Installation

### Prerequisites

- Linux system with systemd (Ubuntu, Debian, etc.)
- Python 3.6 or higher
- Internet connection (for initial dependency installation)

### Automatic Installation

1. Clone or download this repository to your machine
2. Make the installation script executable:
   ```
   chmod +x install.sh
   ```
3. Run the installation script with sudo:
   ```
   sudo ./install.sh
   ```

The script will:
- Install required Python packages
- Create a systemd service for automatic startup
- Start the application
- Configure the service to run on system boot

### Manual Installation

If you prefer to install manually:

1. Install required packages:
   ```
   pip3 install -r requirements.txt
   ```
2. Run the application:
   ```
   python3 app.py
   ```

## Usage

After installation, the application will be available at:

- http://localhost:5000
- http://YOUR_IP_ADDRESS:5000 (accessible across your network)

### Managing the Service

- **Check service status**: `sudo systemctl status wifi-file-transfer`
- **Stop the service**: `sudo systemctl stop wifi-file-transfer`
- **Start the service**: `sudo systemctl start wifi-file-transfer`
- **Restart the service**: `sudo systemctl restart wifi-file-transfer`
- **Disable autostart**: `sudo systemctl disable wifi-file-transfer`

## Uninstallation

To uninstall the application:

1. Make the uninstallation script executable:
   ```
   chmod +x uninstall.sh
   ```
2. Run it with sudo:
   ```
   sudo ./uninstall.sh
   ```

The script will:
- Stop and disable the service
- Remove the service file
- Optionally remove all uploaded files and data

## Troubleshooting

### Service won't start

Check the logs with:
```
journalctl -u wifi-file-transfer
```

### Can't access on another device

- Ensure your firewall allows connections on port 5000
- Check that the server is running with `systemctl status wifi-file-transfer`
- Verify network connectivity between devices

## Security Considerations

This application is designed for use on trusted local networks only. It does not implement authentication or encryption for file transfers.

## License

This project is open source and available under the MIT license. 