"""
Configuration for the WiFi File Transfer application.
This file defines the available storage locations (trans stores) and other settings.
"""

import os
import json
import logging
import shutil
from pathlib import Path

CONFIG_FILE = 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    "service_name": "WiFi File Transfer",
    "max_file_size_gb": 16,  # 16GB max file size
    "allowed_extensions": ["txt", "pdf", "png", "jpg", "jpeg", "gif", "mp3", "mp4", 
                          "zip", "rar", "doc", "docx", "xls", "xlsx", "ppt", "pptx"],
    "trans_stores": [
        {
            "name": "trans_store_1",
            "path": "trans_store",
            "max_size_gb": 0,  # 0 means unlimited (limited only by available disk space)
            "enabled": True
        }
    ]
}

def create_default_config():
    """Create a default configuration file if it doesn't exist"""
    if not os.path.exists(CONFIG_FILE):
        logging.info(f"Creating default configuration file: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    
    # Ensure all trans store directories exist
    config = load_config()
    for store in config.get('trans_stores', []):
        if store.get('enabled', True):
            path = store.get('path')
            if path:
                logging.info(f"Ensuring trans store directory exists: {path}")
                os.makedirs(path, exist_ok=True)

def load_config():
    """Load configuration from file"""
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving configuration: {e}")
        return False

def get_enabled_stores():
    """Get a list of all enabled trans stores"""
    config = load_config()
    stores = []
    
    for store in config.get('trans_stores', []):
        if store.get('enabled', True):
            # Add backwards compatibility for max_size vs max_size_gb
            if 'max_size_gb' in store and 'max_size' not in store:
                # Convert GB to bytes
                store['max_size'] = store['max_size_gb'] * 1024 * 1024 * 1024 if store['max_size_gb'] > 0 else 0
            elif 'max_size' in store and 'max_size_gb' not in store:
                # Calculate GB from bytes for display purposes
                store['max_size_gb'] = store['max_size'] / (1024 * 1024 * 1024) if store['max_size'] > 0 else 0
            
            stores.append(store)
    
    # No sorting by priority - stores will be used in the order they appear in the config
    return stores

def get_store_by_name(name):
    """Get a store by its name"""
    config = load_config()
    for store in config.get('trans_stores', []):
        if store.get('name') == name:
            return store
    return None

def get_max_file_size():
    """Get the maximum allowed file size in bytes"""
    config = load_config()
    # Get max file size in GB, then convert to bytes
    max_size_gb = config.get('max_file_size_gb', DEFAULT_CONFIG['max_file_size_gb'])
    return max_size_gb * 1024 * 1024 * 1024  # Convert GB to bytes

def get_allowed_extensions():
    """Get the list of allowed file extensions"""
    config = load_config()
    return set(config.get('allowed_extensions', DEFAULT_CONFIG['allowed_extensions']))

def get_store_free_space(store_path):
    """Get the available free space in a store in GB"""
    try:
        total, used, free = shutil.disk_usage(store_path)
        free_gb = free / (1024 ** 3)  # Convert to GB
        return free_gb
    except Exception as e:
        logging.error(f"Error getting free space for {store_path}: {e}")
        return 0

def get_store_for_upload(file_size):
    """Find the best store for uploading a file based on available space and order in config"""
    stores = get_enabled_stores()
    
    for store in stores:
        path = store.get('path')
        
        # Check for max_size_gb and convert to bytes if present
        if 'max_size_gb' in store:
            max_store_size_gb = store.get('max_size_gb', 0)
            max_store_size = max_store_size_gb * 1024 * 1024 * 1024 if max_store_size_gb > 0 else 0
        else:
            max_store_size = store.get('max_size', 0)  # 0 means unlimited
        
        # Check if the store exists
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        
        # Get available space
        free_space = get_store_free_space(path) * (1024 ** 3)  # Convert GB to bytes
        
        # Check if this store has enough space
        if file_size <= free_space:
            # Check if adding this file would exceed the store's max size
            if max_store_size > 0:
                # Calculate current store size
                current_size = sum(os.path.getsize(os.path.join(path, f)) 
                                  for f in os.listdir(path) 
                                  if os.path.isfile(os.path.join(path, f)))
                
                # Check if adding this file would exceed the store's max size
                if current_size + file_size > max_store_size:
                    logging.info(f"Store {store['name']} would exceed max size with this file")
                    continue
            
            # This store has enough space and wouldn't exceed max size
            logging.info(f"Selected store {store['name']} for upload of {file_size} bytes")
            return store
    
    # No suitable store found
    logging.warning(f"No suitable store found for upload of {file_size} bytes")
    return None

def get_all_files():
    """Get a list of all files from all enabled trans stores"""
    stores = get_enabled_stores()
    all_files = []
    
    for store in stores:
        store_path = store.get('path')
        store_name = store.get('name')
        
        if os.path.exists(store_path):
            for filename in os.listdir(store_path):
                filepath = os.path.join(store_path, filename)
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    file_modified = os.path.getmtime(filepath)
                    
                    all_files.append({
                        'name': filename,
                        'path': filepath,
                        'size': file_size,
                        'modified': file_modified,
                        'store_name': store_name
                    })
    
    # Sort files by name for consistency
    all_files.sort(key=lambda f: f['name'])
    return all_files

def get_file_by_name(filename):
    """Find a file by its name across all stores"""
    all_files = get_all_files()
    for file in all_files:
        if file['name'] == filename:
            return file
    return None 