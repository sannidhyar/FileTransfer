import os
import socket
import netifaces
from flask import Flask, request, render_template, send_from_directory, jsonify, redirect, url_for, Response, stream_with_context, flash, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from zeroconf import ServiceInfo, Zeroconf
import threading
import time
import json
from datetime import datetime
import io
import logging
import uuid
import config
import shutil

app = Flask(__name__)
CORS(app)

# Load configuration
config.create_default_config()

# Configure app based on loaded settings
app.config['MAX_CONTENT_LENGTH'] = config.get_max_file_size()
app.config['SECRET_KEY'] = str(uuid.uuid4())  # For flash messages

# Configure logging
logging.basicConfig(level=logging.INFO)

# Helper function for server-side file size formatting
def format_file_size(size_bytes):
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

# Template filter for timestamp conversion
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    """Convert a timestamp to a formatted date string"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# Template filter for file size formatting
@app.template_filter('format_size')
def format_size_filter(size):
    """Template filter to format file sizes"""
    return format_file_size(size)

# Helpers
def allowed_file(filename):
    """Check if file has an allowed extension"""
    if '.' not in filename:
        app.logger.warning(f"File '{filename}' has no extension and is not allowed")
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_extensions = config.get_allowed_extensions()
    
    if extension in allowed_extensions:
        return True
    else:
        app.logger.warning(f"File extension '{extension}' from '{filename}' is not in allowed extensions: {allowed_extensions}")
        return False

def get_ip_address():
    """Get the local IP address of the device"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_network_interfaces():
    """Get all network interfaces and their IP addresses"""
    interfaces = []
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
    return interfaces

def get_store_info():
    """Get information about all enabled trans stores"""
    stores = config.get_enabled_stores()
    store_info = []
    
    for index, store in enumerate(stores, 1):
        free_space_gb = config.get_store_free_space(store['path'])
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
    
    return store_info

# Register service with zeroconf for discovery
def register_service(ip, port):
    service_config = config.load_config()
    service_name = service_config.get("service_name", "WiFi File Transfer")
    
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
    print(f"Registering service '{service_name}' on {ip}:{port}")
    zeroconf.register_service(info)
    return zeroconf, info

# Route for the home page
@app.route('/')
def index():
    interfaces = get_network_interfaces()
    
    # Get files from all enabled trans stores
    files = config.get_all_files()
    
    # Get information about the trans stores for display
    stores = get_store_info()
    
    # Load configuration for template
    app_config = config.load_config()
    
    return render_template('index.html', interfaces=interfaces, files=files, stores=stores, config=app_config)

# Upload file route
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Debug information about the request
        app.logger.info(f"Upload request received. Files in request: {list(request.files.keys())}")
        app.logger.info(f"Request form data: {list(request.form.keys())}")
        
        if 'file' not in request.files:
            app.logger.warning("No file part in the request")
            flash('No file part')
            return redirect(request.url)
        
        # Handle multiple files
        files = request.files.getlist('file')
        if not files or all(not file.filename for file in files):
            app.logger.warning("No files selected")
            flash('No selected file')
            return redirect(request.url)
        
        # Save each valid file
        saved_files = []
        for file in files:
            if file and file.filename:
                original_filename = file.filename
                # On some mobile devices, the filename includes a path - extract just the filename
                if '/' in original_filename:
                    original_filename = original_filename.split('/')[-1]
                elif '\\' in original_filename:
                    original_filename = original_filename.split('\\')[-1]
                
                # Check file type
                if not allowed_file(original_filename):
                    app.logger.warning(f"File type not allowed: {original_filename}")
                    flash(f'File type not allowed: {original_filename}. Allowed types: {", ".join(config.get_allowed_extensions())}')
                    continue
                
                filename = secure_filename(original_filename)
                
                # Create a temporary file to get the size
                temp_buffer = io.BytesIO()
                file.save(temp_buffer)
                file_size = temp_buffer.tell()
                temp_buffer.seek(0)  # Reset file pointer for later use
                
                # Check if file exceeds maximum allowed size
                max_file_size = config.get_max_file_size()
                if file_size > max_file_size:
                    app.logger.warning(f"File too large: {filename} ({format_file_size(file_size)})")
                    flash(f'File too large: {filename} ({format_file_size(file_size)}). Maximum allowed size is {config.load_config().get("max_file_size_gb", 16)}GB')
                    continue
                
                # Find the best store for this file
                store = config.get_store_for_upload(file_size)
                
                if store:
                    # Save the file to the selected store
                    filepath = os.path.join(store['path'], filename)
                    with open(filepath, 'wb') as f:
                        f.write(temp_buffer.getvalue())
                    
                    app.logger.info(f"Saved file: {filename} ({format_file_size(file_size)}) to {store['name']}")
                    saved_files.append({
                        'name': filename,
                        'store': store['name']
                    })
                else:
                    app.logger.error(f"No suitable store found for file: {filename} ({format_file_size(file_size)})")
                    flash(f'Not enough space for file: {filename} ({format_file_size(file_size)})')
        
        if saved_files:
            app.logger.info(f"Successfully saved {len(saved_files)} files")
            if len(saved_files) == 1:
                flash(f"File {saved_files[0]['name']} uploaded to {saved_files[0]['store']}")
            else:
                flash(f"Successfully uploaded {len(saved_files)} files")
            return redirect(url_for('index'))
        else:
            app.logger.warning("No valid files were uploaded")
            flash('No valid files were uploaded')
            return redirect(request.url)
    
    # Get store information for the template
    stores = get_store_info()
    
    # Load configuration for template
    app_config = config.load_config()
    
    return render_template('upload.html', stores=stores, config=app_config)

# Modified Download file route with streaming support for speed calculation
@app.route('/download/<filename>')
def download_file(filename):
    # Search for the file in all enabled stores
    all_files = config.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if not file_info:
        flash('File not found')
        return redirect(url_for('index'))
    
    filepath = file_info['path']
    file_size = file_info['size']
    
    # Determine MIME type based on file extension
    mime_type = 'application/octet-stream'  # Default fallback
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
        # Map common extensions to MIME types
        mime_types = {
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
        if ext in mime_types:
            mime_type = mime_types[ext]
    
    app.logger.info(f"Serving file: {filename} ({format_file_size(file_size)}) as {mime_type}")
    
    try:
        # For small files (<50MB), serve directly rather than streaming for better Android compatibility
        if file_size < 50 * 1024 * 1024:  # 50MB
            return send_from_directory(
                directory=os.path.dirname(filepath),
                path=os.path.basename(filepath),
                mimetype=mime_type,
                as_attachment=True,
                download_name=filename
            )
        
        # For larger files, use streaming
        def generate():
            chunk_size = 8192  # 8KB chunks
            with open(filepath, 'rb') as f:
                bytes_sent = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    bytes_sent += len(chunk)
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
        app.logger.error(f"Error serving file {filename}: {str(e)}")
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

# New route to get file info for download tracking
@app.route('/api/file-info/<filename>')
def file_info(filename):
    all_files = config.get_all_files()
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

# Delete file route
@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    all_files = config.get_all_files()
    file_info = next((f for f in all_files if f['name'] == filename), None)
    
    if file_info:
        filepath = file_info['path']
        if os.path.exists(filepath):
            os.remove(filepath)
            app.logger.info(f"Deleted file: {filename} from {file_info['store_name']}")
            return jsonify({'success': True})
    
    app.logger.warning(f"Failed to delete file: {filename}")
    return jsonify({'success': False, 'error': 'File not found'}), 404

# API to list files (for other devices to discover files)
@app.route('/api/files')
def list_files():
    all_files = config.get_all_files()
    
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

# API to get store information
@app.route('/api/stores')
def stores_info():
    return jsonify(get_store_info())

# API to get configuration information
@app.route('/api/config')
def config_info():
    app_config = config.load_config()
    # Only expose necessary configuration
    return jsonify({
        'service_name': app_config.get('service_name', 'WiFi File Transfer'),
        'max_file_size_gb': app_config.get('max_file_size_gb', 16),
        'allowed_extensions': list(config.get_allowed_extensions())
    })

# Direct file access for Android file managers
@app.route('/direct-download/<filename>')
def direct_download(filename):
    """A simpler download route for better Android compatibility"""
    all_files = config.get_all_files()
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
        app.logger.error(f"Error serving file {filename}: {str(e)}")
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

# Main entry point
if __name__ == '__main__':
    ip = get_ip_address()
    port = 5000
    
    # Register with zeroconf in a separate thread
    zeroconf, info = register_service(ip, port)
    
    try:
        print("=" * 50)
        print(f"WiFi File Transfer running at:")
        print(f"http://{ip}:{port}/")
        print("=" * 50)
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
    finally:
        # Unregister on shutdown
        print("Unregistering service...")
        zeroconf.unregister_service(info)
        zeroconf.close() 