document.addEventListener('DOMContentLoaded', function() {
    const socket = io.connect('http://' + document.domain + ':' + location.port);

    socket.on('connect', function() {
        socket.emit('get_progress');
    });

    socket.on('progress_update', function(data) {
        const progressBar = document.getElementById('progress');
        const statusText = document.getElementById('status');

        if (progressBar && statusText) {
            progressBar.value = data.progress;
            statusText.textContent = data.status;
        }
    });

    // Polling for progress if WebSocket fails
    function pollProgress() {
        fetch('/progress', { method: 'GET' })
            .then(response => response.json())
            .then(data => {
                const progressBar = document.getElementById('progress');
                const statusText = document.getElementById('status');

                if (progressBar && statusText) {
                    progressBar.value = data.progress;
                    statusText.textContent = data.status;
                }
            })
            .catch(error => console.error('Error:', error));
    }

    // Fallback to polling if WebSocket connection fails
    let pollTimer;
    socket.on('connect_error', function() {
        console.log('WebSocket connection failed, using polling');
        pollTimer = setInterval(pollProgress, 5000); // Poll every 5 seconds
    });

    // Clear polling interval if WebSocket connection succeeds
    socket.on('connect', function() {
        if (pollTimer) {
            clearInterval(pollTimer);
        }
    });
});