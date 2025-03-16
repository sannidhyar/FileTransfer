document.addEventListener('DOMContentLoaded', function() {
    // Theme management
    initTheme();
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Handle refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            window.location.reload();
        });
    }

    // Handle file deletion
    const deleteButtons = document.querySelectorAll('.delete-file');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filename = this.getAttribute('data-filename');
            if (confirm(`Are you sure you want to delete "${filename}"?`)) {
                deleteFile(filename);
            }
        });
    });

    // Upload form handling
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        const progressBar = document.getElementById('uploadProgressBar');
        const progressDiv = document.getElementById('uploadProgress');
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInput = document.getElementById('file');
        const dropZone = document.getElementById('drop-zone');

        // Setup drag and drop
        if (dropZone) {
            // Prevent default drag behaviors
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, preventDefaults, false);
                document.body.addEventListener(eventName, preventDefaults, false);
            });
            
            // Highlight drop zone when file is dragged over it
            ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, unhighlight, false);
            });
            
            // Handle dropped files
            dropZone.addEventListener('drop', handleDrop, false);
            
            // Add click handler to open file browser
            dropZone.addEventListener('click', function() {
                fileInput.click();
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            function highlight() {
                dropZone.classList.add('active');
            }
            
            function unhighlight() {
                dropZone.classList.remove('active');
            }
            
            function handleDrop(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                fileInput.files = files;
                
                // Update the file selection display
                const fileList = document.getElementById('file-list');
                if (fileList) {
                    fileList.innerHTML = '';
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];
                        const item = document.createElement('li');
                        item.className = 'list-group-item d-flex justify-content-between align-items-center';
                        
                        // Format the file size properly
                        const fileSizeFormatted = formatFileSize(file.size);
                        
                        item.innerHTML = `
                            <span>${file.name}</span>
                            <span class="badge bg-primary rounded-pill">${fileSizeFormatted}</span>
                        `;
                        fileList.appendChild(item);
                    }
                }
            }
        }

        uploadForm.addEventListener('submit', function(e) {
            const fileInput = document.getElementById('file');
            if (fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select at least one file to upload.');
                return;
            }

            progressDiv.classList.remove('d-none');
            uploadBtn.disabled = true;
            
            // In a real implementation, you would use AJAX for progress updates
            // This is just a simple simulation for the UI demo
            let progress = 0;
            const interval = setInterval(() => {
                progress += 5;
                if (progress > 100) {
                    clearInterval(interval);
                    return;
                }
                progressBar.style.width = progress + '%';
                progressBar.textContent = progress + '%';
            }, 300);
        });

        // Update file list when files are selected using the file input
        fileInput.addEventListener('change', function() {
            const fileList = document.getElementById('file-list');
            if (fileList) {
                fileList.innerHTML = '';
                for (let i = 0; i < fileInput.files.length; i++) {
                    const file = fileInput.files[i];
                    const item = document.createElement('li');
                    item.className = 'list-group-item d-flex justify-content-between align-items-center';
                    
                    // Format the file size properly
                    const fileSizeFormatted = formatFileSize(file.size);
                    
                    item.innerHTML = `
                        <span>${file.name}</span>
                        <span class="badge bg-primary rounded-pill">${fileSizeFormatted}</span>
                    `;
                    fileList.appendChild(item);
                }
            }
        });
    }

    // Function to delete a file
    function deleteFile(filename) {
        fetch(`/delete/${encodeURIComponent(filename)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the row from the table
                const fileRow = document.querySelector(`.file-row[data-filename="${filename}"]`);
                if (fileRow) {
                    fileRow.remove();
                }
                
                // Check if there are any files left
                const fileRows = document.querySelectorAll('.file-row');
                if (fileRows.length === 0) {
                    document.getElementById('filesList').innerHTML = `
                        <div class="alert alert-info">
                            <p class="mb-0">No files have been uploaded yet. Use the Upload button to add files.</p>
                        </div>
                    `;
                }
            } else {
                alert('Error deleting file: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while deleting the file.');
        });
    }

    // Theme functions
    function initTheme() {
        // Check for saved theme preference or use browser preference
        const savedTheme = localStorage.getItem('theme') || 
            (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        
        setTheme(savedTheme);
    }
    
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
    }
    
    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update the theme toggle icon
        const themeIcon = document.getElementById('theme-icon');
        
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.classList.remove('bi-moon-fill');
                themeIcon.classList.add('bi-sun-fill');
            } else {
                themeIcon.classList.remove('bi-sun-fill');
                themeIcon.classList.add('bi-moon-fill');
            }
        }
    }

    // Intercept download links to show progress
    const downloadLinks = document.querySelectorAll('a[href^="/download/"]');
    downloadLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const downloadUrl = this.getAttribute('href');
            const filename = downloadUrl.split('/').pop();
            
            // Get file info first
            fetch(`/api/file-info/${encodeURIComponent(filename)}`)
                .then(response => response.json())
                .then(fileInfo => {
                    if (fileInfo.error) {
                        alert('Error: ' + fileInfo.error);
                        return;
                    }
                    
                    // Setup and show download modal
                    const downloadModal = new bootstrap.Modal(document.getElementById('downloadModal'));
                    document.getElementById('downloading-filename').textContent = filename;
                    document.getElementById('download-total').textContent = formatFileSize(fileInfo.size);
                    
                    // Reset progress UI
                    const progressBar = document.getElementById('download-progress-bar');
                    progressBar.style.width = '0%';
                    progressBar.textContent = '0%';
                    document.getElementById('download-speed').textContent = '0 KB/s';
                    document.getElementById('download-current').textContent = '0 KB';
                    document.getElementById('download-eta').textContent = 'Calculating...';
                    
                    downloadModal.show();
                    
                    // Start the actual download with progress tracking
                    trackDownload(downloadUrl, fileInfo.size);
                })
                .catch(error => {
                    console.error('Error fetching file info:', error);
                    // Fall back to regular download if tracking fails
                    window.location.href = downloadUrl;
                });
        });
    });

    // Track download progress and speed
    function trackDownload(url, totalSize) {
        // Create a hidden iframe to handle the download
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        
        // Variables for speed calculation
        let startTime = Date.now();
        let lastUpdateTime = startTime;
        let bytesLoaded = 0;
        let lastBytesLoaded = 0;
        let downloadSpeed = 0;
        
        // Use XHR to track progress
        const xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.responseType = 'blob';
        
        xhr.onprogress = function(event) {
            if (event.lengthComputable) {
                bytesLoaded = event.loaded;
                const currentTime = Date.now();
                const timeDiff = (currentTime - lastUpdateTime) / 1000; // in seconds
                
                if (timeDiff > 0.5) { // Update every half second
                    // Calculate speed
                    const bytesDiff = bytesLoaded - lastBytesLoaded;
                    downloadSpeed = bytesDiff / timeDiff; // bytes per second
                    
                    // Update UI
                    const progressPercent = Math.round((bytesLoaded / totalSize) * 100);
                    const progressBar = document.getElementById('download-progress-bar');
                    progressBar.style.width = progressPercent + '%';
                    progressBar.textContent = progressPercent + '%';
                    
                    document.getElementById('download-speed').textContent = formatFileSize(downloadSpeed) + '/s';
                    document.getElementById('download-current').textContent = formatFileSize(bytesLoaded);
                    
                    // Calculate ETA
                    const bytesRemaining = totalSize - bytesLoaded;
                    if (downloadSpeed > 0) {
                        const secondsRemaining = Math.round(bytesRemaining / downloadSpeed);
                        document.getElementById('download-eta').textContent = formatTime(secondsRemaining);
                    }
                    
                    // Update for next calculation
                    lastUpdateTime = currentTime;
                    lastBytesLoaded = bytesLoaded;
                }
            }
        };
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                // Download complete - update UI to 100%
                const progressBar = document.getElementById('download-progress-bar');
                progressBar.style.width = '100%';
                progressBar.textContent = '100%';
                document.getElementById('download-eta').textContent = 'Download complete!';
                
                // Create a download link
                const blob = xhr.response;
                const downloadUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = downloadUrl;
                a.download = url.split('/').pop();
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                setTimeout(function() {
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(downloadUrl);
                }, 100);
            }
        };
        
        xhr.onerror = function() {
            console.error('Download failed');
            alert('Download failed. Please try again.');
            
            // Fall back to direct download
            iframe.src = url;
        };
        
        xhr.send();
    }

    // Helper function to format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        // Force GB for files larger than 900MB
        if (bytes > 900 * 1024 * 1024) {
            return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
        }
        
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 4);
        
        // Explicitly handle each size category for better control
        if (i === 0) { // Bytes
            return bytes + ' ' + sizes[i];
        } else if (i === 1) { // KB
            return (bytes / 1024).toFixed(2) + ' ' + sizes[i];
        } else if (i === 2) { // MB
            return (bytes / (1024 * 1024)).toFixed(2) + ' ' + sizes[i];
        } else if (i === 3) { // GB
            return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' ' + sizes[i];
        } else { // TB
            return (bytes / (1024 * 1024 * 1024 * 1024)).toFixed(2) + ' ' + sizes[i];
        }
    }
    
    // Helper function to format time
    function formatTime(seconds) {
        if (seconds < 60) {
            return seconds + ' sec';
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            return minutes + ' min ' + remainingSeconds + ' sec';
        } else {
            const hours = Math.floor(seconds / 3600);
            const remainingMinutes = Math.floor((seconds % 3600) / 60);
            return hours + ' hr ' + remainingMinutes + ' min';
        }
    }

    // Add service worker for PWA support
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then(function(registration) {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch(function(error) {
                console.log('Service Worker registration failed:', error);
            });
    }
}); 