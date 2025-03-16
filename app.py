import os
import socket
import netifaces
from flask import (
    Flask, request, render_template, send_from_directory, jsonify, 
    redirect, url_for, Response, stream_with_context, flash, session, 
    current_app, g
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from zeroconf import ServiceInfo, Zeroconf
import threading
import time
from datetime import datetime
import io
import logging
import uuid
import config
import shutil
import argparse
from functools import wraps, lru_cache
from typing import Dict, List, Any, Optional, Callable, Tuple, Union, Set, Generator

# Initialize configuration instance early
config_instance = config.Configuration.get_instance()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='WiFi File Transfer')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--config', type=str, default="./config.json", help='Path to the configuration file (json)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='Host to run the server on')
    return parser.parse_args()

# Parse arguments early to configure the application
args = parse_args()

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('wifi_file_transfer')
logger.info("Starting WiFi File Transfer application")

# Set custom config file path if provided
if args.config:
    config.set_config_file(args.config)
    logger.info(f"Using configuration file: {args.config}")

# Initialize configuration - do this early
config_instance.create_default_config()

# Initialize Flask application
app = Flask(__name__)
CORS(app)

# Configure app based on loaded settings
app.config['MAX_CONTENT_LENGTH'] = config_instance.get_max_file_size()
app.config['SECRET_KEY'] = str(uuid.uuid4())  # For flash messages

# Global variables
CHUNK_SIZE = 8192  # 8KB chunks for file streaming
SMALL_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB threshold for direct vs. streaming download

# Cache for network interfaces - refreshed periodically
_network_interfaces_cache = None
_network_cache_timestamp = 0
_NETWORK_CACHE_TTL = 60  # seconds

# Cache for mime types
_mime_types = {
    'pdf': 'application/pdf',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'mp3': 'audio/mpeg',
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'txt': 'text/plain',
    'html': 'text/html',
    'css': 'text/css',
    'js': 'application/javascript',
    'json': 'application/json',
    'zip': 'application/zip',
    'rar': 'application/x-rar-compressed',
    'tar': 'application/x-tar',
    'gz': 'application/gzip',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ppt': 'application/vnd.ms-powerpoint',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'mkv': 'video/x-matroska'
}

# Helper Functions
def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    # Force GB for files larger than 900MB
    if size_bytes > 900 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

# Template filters
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp: float) -> str:
    """Convert a timestamp to a formatted date string"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('format_size')
def format_size_filter(size: int) -> str:
    """Template filter to format file sizes"""
    return format_file_size(size)

# Error handling decorator
def handle_errors(f):
    """Decorator to handle errors in routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            flash(f"An error occurred: {str(e)}")
            return redirect(url_for('index'))
    return decorated_function

# Helpers
def allowed_file(filename: str) -> bool:
    """Check if file has an allowed extension"""
    if '.' not in filename:
        logger.warning(f"File '{filename}' has no extension and is not allowed")
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_extensions = config_instance.get_allowed_extensions()
    
    if extension in allowed_extensions:
        return True
    else:
        logger.warning(f"File extension '{extension}' from '{filename}' is not in allowed extensions: {allowed_extensions}")
        return False

def get_ip_address() -> str:
    """Get the local IP address of the device"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception as e:
        logger.warning(f"Error getting IP address: {e}")
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_network_interfaces() -> List[Dict[str, str]]:
    """Get all network interfaces and their IP addresses with caching"""
    global _network_interfaces_cache, _network_cache_timestamp
    
    # Return cached value if still valid
    current_time = time.time()
    if _network_interfaces_cache is not None and current_time - _network_cache_timestamp < _NETWORK_CACHE_TTL:
        return _network_interfaces_cache
    
    interfaces = []
    try:
        for interface_name in netifaces.interfaces():
            addresses = netifaces.ifaddresses(interface_name)
            if netifaces.AF_INET in addresses:
                for link in addresses[netifaces.AF_INET]:
                    ip_address = link['addr']
                    if ip_address != '127.0.0.1':
                        interfaces.append({
                            'name': interface_name,
                            'ip': ip_address
                        })
    except Exception as e:
        logger.error(f"Error getting network interfaces: {e}")
    
    # Update cache
    _network_interfaces_cache = interfaces
    _network_cache_timestamp = current_time
    
    return interfaces

def get_store_info() -> List[Dict[str, Any]]:
    """Get information about all enabled trans stores"""
    stores = config_instance.get_enabled_stores()
    store_info = []
    
    for index, store in enumerate(stores, 1):
        try:
            free_space_gb = config_instance.get_store_free_space(store['path'])
            total, used, free = shutil.disk_usage(store['path'])
            total_gb = total / (1024 ** 3)
            
            # Count files in this store
            file_count = 0
            if os.path.exists(store['path']):
                file_count = len([f for f in os.listdir(store['path']) if os.path.isfile(os.path.join(store['path'], f))])
            
            store_info.append({
                'name': store['name'],
                'path': store['path'],
                'free_space_gb': round(free_space_gb, 2),
                'total_space_gb': round(total_gb, 2),
                'usage_percent': round((total - free) / total * 100, 2) if total > 0 else 0,
                'store_number': index,  # Sequential number based on order in config
                'file_count': file_count
            })
        except Exception as e:
            logger.error(f"Error getting store info for {store['name']}: {e}")
            # Include basic info
            store_info.append({
                'name': store['name'],
                'path': store['path'],
                'error': str(e),
                'free_space_gb': 0,
                'total_space_gb': 0,
                'usage_percent': 0,
                'store_number': index,
                'file_count': 0
            })
    
    return store_info

def get_mime_type(filename: str) -> str:
    """Determine MIME type based on file extension"""
    default_mime = 'application/octet-stream'  # Default fallback
    if '.' not in filename:
        return default_mime
        
    ext = filename.rsplit('.', 1)[1].lower()
    return _mime_types.get(ext, default_mime)

# Register service with zeroconf for discovery
def register_service(ip: str, port: int) -> Tuple[Zeroconf, ServiceInfo]:
    """Register the service with zeroconf for discovery"""
    app_config = config_instance.get_config()
    service_name = app_config.get("service_name", "WiFi File Transfer")
    
    hostname = socket.gethostname()
    info = ServiceInfo(
        "_wifitransfer._tcp.local.",
        f"{hostname}._wifitransfer._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={
            b'name': service_name.encode('utf-8'),
            b'path': b'/files'
        }
    )
    
    zeroconf = Zeroconf()
    logger.info(f"Registering service '{service_name}' on {ip}:{port}")
    try:
        zeroconf.register_service(info)
        return zeroconf, info
    except Exception as e:
        logger.error(f"Error registering service: {e}")
        return zeroconf, info

# Route handlers
@app.route('/')
@handle_errors
def index():
    """Render the home page"""
    interfaces = get_network_interfaces()
    
    # Get files from all enabled trans stores
    files = config_instance.get_all_files()
    
    # Get information about the trans stores for display
    stores = get_store_info()
    
    # Load configuration for template
    app_config = config_instance.get_config()
    
    return render_template('index.html', interfaces=interfaces, files=files, stores=stores, config=app_config)

@app.route('/upload', methods=['GET', 'POST'])
@handle_errors
def upload_file():
    """Handle file uploads"""
    if request.method == 'POST':
        # Debug information about the request
        logger.info(f"Upload request received. Files in request: {list(request.files.keys())}")
        logger.info(f"Request form data: {list(request.form.keys())}")
        
        if 'file' not in request.files:
            logger.warning("No file part in the request")
            flash('No file part')
            return redirect(request.url)
        
        # Handle multiple files
        files = request.files.getlist('file')
        if not files or all(not file.filename for file in files):
            logger.warning("No files selected")
            flash('No selected file')
            return redirect(request.url)
        
        # Save each valid file
        saved_files = []
        failed_files = []
        
        for file in files:
            if file and file.filename:
                try:
                    # Process the file
                    result = process_upload_file(file)
                    if result['success']:
                        saved_files.append(result['file_info'])
                    else:
                        failed_files.append(result['error'])
                except Exception as e:
                    logger.error(f"Error processing file {file.filename}: {e}", exc_info=True)
                    failed_files.append({
                        'name': file.filename,
                        'error': str(e)
                    })
        
        # Show results
        if saved_files:
            logger.info(f"Successfully saved {len(saved_files)} files")
            if len(saved_files) == 1:
                flash(f"File {saved_files[0]['name']} uploaded to {saved_files[0]['store']}")
            else:
                flash(f"Successfully uploaded {len(saved_files)} files")
                
        if failed_files:
            logger.warning(f"Failed to upload {len(failed_files)} files")
            for fail in failed_files:
                flash(f"Failed to upload {fail.get('name', 'unknown file')}: {fail.get('error', 'unknown error')}")
                
        if saved_files:
            return redirect(url_for('index'))
        else:
            flash('No valid files were uploaded')
            return redirect(request.url)
    
    # GET request - show upload form
    stores = get_store_info()
    app_config = config_instance.get_config()
    
    return render_template('upload.html', stores=stores, config=app_config)

def process_upload_file(file) -> Dict[str, Any]:
    """Process an uploaded file"""
    original_filename = file.filename
    
    # On some mobile devices, the filename includes a path - extract just the filename
    if '/' in original_filename:
        original_filename = original_filename.split('/')[-1]
    elif '\\' in original_filename:
        original_filename = original_filename.split('\\')[-1]
    
    # Check file type
    if not allowed_file(original_filename):
        logger.warning(f"File type not allowed: {original_filename}")
        return {
            'success': False,
            'error': {
                'name': original_filename,
                'error': f'File type not allowed. Allowed types: {", ".join(config_instance.get_allowed_extensions())}'
            }
        }
    
    filename = secure_filename(original_filename)
    
    # Create a temporary file to get the size
    temp_buffer = io.BytesIO()
    file.save(temp_buffer)
    file_size = temp_buffer.tell()
    temp_buffer.seek(0)  # Reset file pointer for later use
    
    # Check if file exceeds maximum allowed size
    max_file_size = config_instance.get_max_file_size()
    if file_size > max_file_size:
        logger.warning(f"File too large: {filename} ({format_file_size(file_size)})")
        return {
            'success': False,
            'error': {
                'name': filename,
                'error': f'File too large: {format_file_size(file_size)}. Maximum allowed size is {config_instance.get_config().get("max_file_size_gb", 16)}GB'
            }
        }
    
    # Find the best store for this file
    store = config_instance.get_store_for_upload(file_size)
    
    if not store:
        logger.error(f"No suitable store found for file: {filename} ({format_file_size(file_size)})")
        return {
            'success': False,
            'error': {
                'name': filename,
                'error': f'Not enough space for file: {format_file_size(file_size)}'
            }
        }
        
    # Save the file to the selected store
    filepath = os.path.join(store['path'], filename)
    with open(filepath, 'wb') as f:
        f.write(temp_buffer.getvalue())
    
    logger.info(f"Saved file: {filename} ({format_file_size(file_size)}) to {store['name']}")
    return {
        'success': True,
        'file_info': {
            'name': filename,
            'store': store['name'],
            'size': file_size,
            'path': filepath
        }
    }

@app.route('/download/<filename>')
@handle_errors
def download_file(filename: str):
    """Download a file with support for streaming large files"""
    # Search for the file in all enabled stores
    all_files = config_instance.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if not file_info:
        flash('File not found')
        return redirect(url_for('index'))
    
    filepath = file_info['path']
    file_size = file_info['size']
    mime_type = get_mime_type(filename)
    
    logger.info(f"Serving file: {filename} ({format_file_size(file_size)}) as {mime_type}")
    
    try:
        # For small files (<50MB), serve directly rather than streaming for better Android compatibility
        if file_size < SMALL_FILE_THRESHOLD:
            return send_from_directory(
                directory=os.path.dirname(filepath),
                path=os.path.basename(filepath),
                mimetype=mime_type,
                as_attachment=True,
                download_name=filename
            )
        
        # For larger files, use streaming
        def generate() -> Generator[bytes, None, None]:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(file_size),
            'X-File-Size': str(file_size),
            'Cache-Control': 'no-cache',
            'Content-Type': mime_type
        }
        
        return Response(
            stream_with_context(generate()),
            headers=headers,
            mimetype=mime_type,
            direct_passthrough=True
        )
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}", exc_info=True)
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/api/file-info/<filename>')
@handle_errors
def file_info(filename: str):
    """Get information about a file"""
    all_files = config_instance.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if not file_info:
        return jsonify({'error': 'File not found'}), 404
    
    return jsonify({
        'name': filename,
        'size': file_info['size'],
        'size_formatted': format_file_size(file_info['size']),
        'modified': file_info['modified'],
        'store': file_info['store_name']
    })

@app.route('/delete/<filename>', methods=['POST'])
@handle_errors
def delete_file(filename: str):
    """Delete a file"""
    all_files = config_instance.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if file_info:
        filepath = file_info['path']
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted file: {filename} from {file_info['store_name']}")
            # Refresh the files cache
            config_instance.get_all_files(force_refresh=True)
            return jsonify({'success': True})
    
    logger.warning(f"Failed to delete file: {filename}")
    return jsonify({'success': False, 'error': 'File not found'}), 404

@app.route('/api/files')
@handle_errors
def list_files():
    """API endpoint to list all files"""
    all_files = config_instance.get_all_files()
    
    # Format for API response
    files_api = []
    for file in all_files:
        files_api.append({
            'name': file['name'],
            'size': file['size'],
            'size_formatted': format_file_size(file['size']),
            'modified': file['modified'],
            'download_url': f"/download/{file['name']}",
            'store': file['store_name']
        })
    
    return jsonify(files_api)

@app.route('/api/stores')
@handle_errors
def stores_info():
    """API endpoint to get store information"""
    return jsonify(get_store_info())

@app.route('/api/config')
@handle_errors
def config_info():
    """API endpoint to get configuration information"""
    app_config = config_instance.get_config()
    # Only expose necessary configuration
    return jsonify({
        'service_name': app_config.get('service_name', 'WiFi File Transfer'),
        'max_file_size_gb': app_config.get('max_file_size_gb', 16),
        'allowed_extensions': list(config_instance.get_allowed_extensions())
    })

@app.route('/direct-download/<filename>')
@handle_errors
def direct_download(filename: str):
    """A simpler download route for better Android compatibility"""
    all_files = config_instance.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if not file_info:
        flash('File not found')
        return redirect(url_for('index'))
    
    filepath = file_info['path']
    
    # For Android, simpler direct download is more reliable
    try:
        return send_from_directory(
            directory=os.path.dirname(filepath),
            path=os.path.basename(filepath),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}", exc_info=True)
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {str(e)}", exc_info=True)
    return render_template('error.html', error='Server error'), 500

# Main entry point
if __name__ == '__main__':
    ip = get_ip_address()
    
    # Register with zeroconf in a separate thread
    zeroconf, info = register_service(ip, args.port)
    
    try:
        logger.info("=" * 50)
        logger.info(f"WiFi File Transfer running at:")
        logger.info(f"http://{ip}:{args.port}/")
        logger.info(f"Using configuration file: {config_instance.config_file}")
        logger.info("=" * 50)
        
        # Print to console as well
        print("=" * 50)
        print(f"WiFi File Transfer running at:")
        print(f"http://{ip}:{args.port}/")
        print(f"Using configuration file: {config_instance.config_file}")
        print("=" * 50)
        
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    finally:
        # Unregister on shutdown
        logger.info("Unregistering service...")
        try:
            zeroconf.unregister_service(info)
            zeroconf.close()
        except Exception as e:
            logger.error(f"Error unregistering service: {e}") 