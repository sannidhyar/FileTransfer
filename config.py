"""
Configuration for the WiFi File Transfer application.
This file defines the available storage locations (trans stores) and other settings.
"""

import os
import json
import logging
import shutil
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Optional, Set, Any, Union

# Get the logger for this module
logger = logging.getLogger('wifi_file_transfer.config')

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

class Configuration:
    """Singleton class to manage application configuration with efficient caching."""
    
    _instance = None
    
    # Constants for unit conversions
    _GB_TO_BYTES = 1024 * 1024 * 1024

    @classmethod
    def get_instance(cls) -> 'Configuration':
        """Get the singleton instance of Configuration"""
        if cls._instance is None:
            cls._instance = Configuration()
        return cls._instance

    def __init__(self) -> None:
        """Initialize the configuration"""
        # Default configuration file path
        self.config_file = 'config.json'
        self._config_data = None
        self._stores_cache = None
        self._all_files_cache = None
        self._cache_timestamp = 0
        
    def set_config_file(self, path: str) -> str:
        """Set the configuration file path and reset caches"""
        self.config_file = path
        logger.info(f"Configuration file path set to: {self.config_file}")
        # Reset all caches
        self.clear_caches()
        return self.config_file
    
    def clear_caches(self) -> None:
        """Clear all cached data to force reloading from disk"""
        self._config_data = None
        self._stores_cache = None
        self._all_files_cache = None
        self._cache_timestamp = 0
        # Clear lru_cache decorated methods
        self.get_allowed_extensions.cache_clear()
        self.get_max_file_size.cache_clear()

    def config_dir(self) -> str:
        """Get the directory containing the configuration file"""
        return os.path.dirname(self.config_file) or '.'
        
    def create_default_config(self) -> Dict[str, Any]:
        """Create a default configuration file if it doesn't exist"""
        # Check if file exists
        if not os.path.exists(self.config_file):
            # Make sure the directory exists
            config_dir = self.config_dir()
            if config_dir and not os.path.exists(config_dir):
                logger.info(f"Creating configuration directory: {config_dir}")
                os.makedirs(config_dir, exist_ok=True)
                
            logger.info(f"Creating default configuration file: {self.config_file}")
            with open(self.config_file, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            logger.info(f"Default configuration file created successfully")
            # Set the default config as our in-memory config
            self._config_data = DEFAULT_CONFIG.copy()
        else:
            logger.info(f"Configuration file already exists: {self.config_file}")
            # Load the existing configuration
            self._load_config_from_file()
        
        # Process and ensure all trans store directories exist
        self._process_trans_stores()
        
        return self.get_config()

    def _process_trans_stores(self) -> None:
        """Process trans stores ensuring directories exist and handling inaccessible stores"""
        inaccessible_stores = []
        
        for store in self.get_config().get('trans_stores', []):
            if store.get('enabled', True):
                path = store.get('path')
                if path:
                    try:
                        logger.info(f"Ensuring trans store directory exists: {path}")
                        os.makedirs(path, exist_ok=True)
                    except (PermissionError, OSError) as e:
                        # Store isn't accessible - log and add to list of inaccessible stores
                        error_msg = f"WARNING: Trans store '{store.get('name')}' at path '{path}' is not accessible: {str(e)}"
                        logger.warning(error_msg)
                        inaccessible_stores.append({
                            'name': store.get('name'),
                            'path': path,
                            'error': str(e)
                        })
        
        if inaccessible_stores:
            self._handle_inaccessible_stores(inaccessible_stores)

    def _handle_inaccessible_stores(self, inaccessible_stores: List[Dict[str, str]]) -> None:
        """Handle inaccessible stores by logging warnings and creating temporary config"""
        warning_msg = f"\n{'='*80}\n"
        warning_msg += f"WARNING: {len(inaccessible_stores)} trans store(s) are not accessible!\n"
        warning_msg += f"The application will continue but these stores will be ignored:\n"
        for i, store in enumerate(inaccessible_stores, 1):
            warning_msg += f"  {i}. {store['name']} ({store['path']}): {store['error']}\n"
        warning_msg += f"{'='*80}\n"
        logger.warning(warning_msg)
        
        # Consider saving a temporary config without the inaccessible stores
        if len(inaccessible_stores) < len(self.get_config().get('trans_stores', [])):
            # We still have some accessible stores - create a temporary runtime config
            logger.info("Creating temporary runtime config with only accessible stores")
            # Filter out inaccessible stores
            accessible_stores = [s for s in self.get_config().get('trans_stores', []) 
                               if not any(ias['name'] == s['name'] for ias in inaccessible_stores)]
            temp_config = self.get_config().copy()
            temp_config['trans_stores'] = accessible_stores
            # Only update in-memory config, don't save to disk
            self._config_data = temp_config
            # Force refresh of stores cache
            self._stores_cache = None

    def _load_config_from_file(self) -> Dict[str, Any]:
        """Low level method to load configuration directly from file"""
        try:
            with open(self.config_file, 'r') as f:
                self._config_data = json.load(f)
            return self._config_data
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self._config_data = DEFAULT_CONFIG.copy()
            return self._config_data

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file with error handling"""
        if not os.path.exists(self.config_file):
            return self.create_default_config()
        
        return self._load_config_from_file()

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to file and update caches"""
        if config is None:
            config = self.get_config()
            
        try:
            # Ensure the directory exists
            config_dir = self.config_dir()
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
                
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            # Update in-memory config
            self._config_data = config
            # Clear caches since config has changed
            self.clear_caches()
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
            
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration with lazy loading"""
        if self._config_data is None:
            self.load_config()
        return self._config_data
        
    def is_config_stale(self) -> bool:
        """Check if the config file has been modified since last load"""
        if not os.path.exists(self.config_file):
            return False
            
        current_mtime = os.path.getmtime(self.config_file)
        return current_mtime > self._cache_timestamp

    def reload_if_needed(self) -> bool:
        """Reload config if the file has changed on disk"""
        if self.is_config_stale():
            logger.info(f"Configuration file has changed, reloading")
            self.clear_caches()
            self.load_config()
            return True
        return False

    def get_enabled_stores(self) -> List[Dict[str, Any]]:
        """Get a list of all enabled trans stores with caching"""
        # Check if config is stale before using cache
        self.reload_if_needed()
        
        # Use cached value if available
        if self._stores_cache is not None:
            return self._stores_cache
            
        stores = []
        
        for store in self.get_config().get('trans_stores', []):
            if store.get('enabled', True):
                # Make a copy to avoid modifying the original
                store_copy = store.copy()
                
                # Add backwards compatibility for max_size vs max_size_gb
                self._normalize_store_size_fields(store_copy)
                
                stores.append(store_copy)
        
        # Cache the result
        self._stores_cache = stores
        return stores

    def _normalize_store_size_fields(self, store: Dict[str, Any]) -> None:
        """Normalize size fields in store config for backwards compatibility"""
        if 'max_size_gb' in store and 'max_size' not in store:
            # Convert GB to bytes
            store['max_size'] = store['max_size_gb'] * self._GB_TO_BYTES if store['max_size_gb'] > 0 else 0
        elif 'max_size' in store and 'max_size_gb' not in store:
            # Calculate GB from bytes for display purposes
            store['max_size_gb'] = store['max_size'] / self._GB_TO_BYTES if store['max_size'] > 0 else 0

    def get_store_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a store by its name with efficient lookup"""
        for store in self.get_enabled_stores():
            if store.get('name') == name:
                return store
        return None

    @lru_cache(maxsize=1)
    def get_max_file_size(self) -> int:
        """Get the maximum allowed file size in bytes with caching"""
        # Get max file size in GB, then convert to bytes
        max_size_gb = self.get_config().get('max_file_size_gb', DEFAULT_CONFIG['max_file_size_gb'])
        return max_size_gb * self._GB_TO_BYTES  # Convert GB to bytes

    @lru_cache(maxsize=1)
    def get_allowed_extensions(self) -> Set[str]:
        """Get the list of allowed file extensions with caching"""
        return set(self.get_config().get('allowed_extensions', DEFAULT_CONFIG['allowed_extensions']))

    def get_store_free_space(self, store_path: str) -> float:
        """Get the available free space in a store in GB"""
        try:
            # Check if path exists and is accessible first
            if not os.path.exists(store_path):
                logger.warning(f"Store path does not exist: {store_path}")
                return 0
                
            total, used, free = shutil.disk_usage(store_path)
            free_gb = free / self._GB_TO_BYTES  # Convert to GB
            return free_gb
        except Exception as e:
            logger.error(f"Error getting free space for {store_path}: {e}")
            return 0

    def get_store_for_upload(self, file_size: int) -> Optional[Dict[str, Any]]:
        """Find the best store for uploading a file based on available space and order in config"""
        stores = self.get_enabled_stores()
        
        for store in stores:
            path = store.get('path')
            
            # Get max store size
            max_store_size = self._get_store_max_size(store)
            
            # Check if the store exists
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            
            # Get available space
            free_space = self.get_store_free_space(path) * self._GB_TO_BYTES  # Convert GB to bytes
            
            # Check if this store has enough space
            if file_size <= free_space:
                # Check if adding this file would exceed the store's max size
                if max_store_size > 0 and not self._store_can_fit_file(path, file_size, max_store_size):
                    logger.info(f"Store {store['name']} would exceed max size with this file")
                    continue
                
                # This store has enough space and wouldn't exceed max size
                logger.info(f"Selected store {store['name']} for upload of {file_size} bytes")
                return store
        
        # No suitable store found
        logger.warning(f"No suitable store found for upload of {file_size} bytes")
        return None

    def _get_store_max_size(self, store: Dict[str, Any]) -> int:
        """Get the maximum size of a store in bytes"""
        if 'max_size_gb' in store:
            max_store_size_gb = store.get('max_size_gb', 0)
            return max_store_size_gb * self._GB_TO_BYTES if max_store_size_gb > 0 else 0
        else:
            return store.get('max_size', 0)  # 0 means unlimited
            
    def _store_can_fit_file(self, path: str, file_size: int, max_store_size: int) -> bool:
        """Check if a file can fit in a store without exceeding maximum size"""
        # Calculate current store size
        current_size = sum(os.path.getsize(os.path.join(path, f)) 
                           for f in os.listdir(path) 
                           if os.path.isfile(os.path.join(path, f)))
        
        # Check if adding this file would exceed the store's max size
        return current_size + file_size <= max_store_size

    def get_all_files(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get a list of all files from all enabled trans stores with caching"""
        # Force refresh or reload if needed
        if force_refresh or self.reload_if_needed() or self._all_files_cache is None:
            self._refresh_files_cache()
            
        return self._all_files_cache
        
    def _refresh_files_cache(self) -> None:
        """Refresh the files cache"""
        stores = self.get_enabled_stores()
        all_files = []
        
        for store in stores:
            store_path = store.get('path')
            store_name = store.get('name')
            
            if os.path.exists(store_path):
                try:
                    # Use os.scandir for better performance
                    with os.scandir(store_path) as entries:
                        for entry in entries:
                            if entry.is_file():
                                try:
                                    stat = entry.stat()
                                    all_files.append({
                                        'name': entry.name,
                                        'path': os.path.join(store_path, entry.name),
                                        'size': stat.st_size,
                                        'modified': stat.st_mtime,
                                        'store_name': store_name
                                    })
                                except (PermissionError, OSError) as e:
                                    logger.warning(f"Error accessing file {entry.name}: {e}")
                except (PermissionError, OSError) as e:
                    logger.warning(f"Error accessing store directory {store_path}: {e}")
        
        # Sort files by name for consistency
        all_files.sort(key=lambda f: f['name'])
        self._all_files_cache = all_files
        # Update cache timestamp
        self._cache_timestamp = time.time() if 'time' in globals() else os.path.getmtime(self.config_file)

    def get_file_by_name(self, filename: str) -> Optional[Dict[str, Any]]:
        """Find a file by its name across all stores"""
        all_files = self.get_all_files()
        for file in all_files:
            if file['name'] == filename:
                return file
        return None

    def refresh_caches(self) -> None:
        """Refresh all caches manually"""
        self.clear_caches()
        self.get_config()
        self.get_enabled_stores()
        self.get_all_files(force_refresh=True)

# Ensure we import time module for cache timestamp
import time

# Create a global instance of the Configuration class for backward compatibility
# This allows existing code to use config.X functions
config_instance = Configuration.get_instance()

# Define module-level functions that delegate to the config_instance
def set_config_file(path: str) -> str:
    return config_instance.set_config_file(path)

def create_default_config() -> Dict[str, Any]:
    return config_instance.create_default_config()

def load_config() -> Dict[str, Any]:
    return config_instance.load_config()

def save_config(config: Optional[Dict[str, Any]] = None) -> bool:
    return config_instance.save_config(config)

def get_enabled_stores() -> List[Dict[str, Any]]:
    return config_instance.get_enabled_stores()

def get_store_by_name(name: str) -> Optional[Dict[str, Any]]:
    return config_instance.get_store_by_name(name)

def get_max_file_size() -> int:
    return config_instance.get_max_file_size()

def get_allowed_extensions() -> Set[str]:
    return config_instance.get_allowed_extensions()

def get_store_free_space(store_path: str) -> float:
    return config_instance.get_store_free_space(store_path)

def get_store_for_upload(file_size: int) -> Optional[Dict[str, Any]]:
    return config_instance.get_store_for_upload(file_size)

def get_all_files(force_refresh: bool = False) -> List[Dict[str, Any]]:
    return config_instance.get_all_files(force_refresh)

def get_file_by_name(filename: str) -> Optional[Dict[str, Any]]:
    return config_instance.get_file_by_name(filename)

def refresh_caches() -> None:
    """Refresh all caches manually"""
    config_instance.refresh_caches()

# Define a property for backward compatibility for code that accesses CONFIG_FILE directly
CONFIG_FILE = config_instance.config_file 