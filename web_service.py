"""
Flask Web Service for Serial to TCP Forwarder Configuration and Monitoring
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import threading
import logging
from serial_forwarder import SerialToTCPForwarder

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# Initialize forwarder
forwarder = None
forwarder_lock = threading.Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current forwarder status"""
    with forwarder_lock:
        if forwarder:
            status = forwarder.get_status()
            status['running'] = forwarder.running
            return jsonify(status)
        else:
            return jsonify({
                'running': False,
                'serial_connected': False,
                'tcp_connected': False,
                'buffer_size': 0,
                'messages_sent': 0,
                'messages_buffered': 0,
                'last_error': 'Forwarder not initialized'
            })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    with forwarder_lock:
        if forwarder:
            return jsonify(forwarder.config)
        else:
            # Return default config
            temp_forwarder = SerialToTCPForwarder()
            return jsonify(temp_forwarder.get_default_config())


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.get_json()
        
        # Validate configuration
        required_fields = ['serial_port', 'serial_baudrate', 'tcp_host', 'tcp_port']
        for field in required_fields:
            if field not in new_config:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        with forwarder_lock:
            global forwarder
            
            # Stop existing forwarder if running
            was_running = False
            if forwarder and forwarder.running:
                was_running = True
                forwarder.stop()
            
            # Create new forwarder with updated config
            if forwarder:
                forwarder.save_config(new_config)
            else:
                forwarder = SerialToTCPForwarder()
                forwarder.save_config(new_config)
            
            # Restart if it was running
            if was_running:
                forwarder.start()
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_forwarder():
    """Start the forwarder"""
    try:
        with forwarder_lock:
            global forwarder
            
            if not forwarder:
                forwarder = SerialToTCPForwarder()
            
            if forwarder.running:
                return jsonify({'success': False, 'error': 'Forwarder is already running'})
            
            success = forwarder.start()
            
            if success:
                return jsonify({'success': True, 'message': 'Forwarder started successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to start forwarder'})
    
    except Exception as e:
        logger.error(f"Error starting forwarder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_forwarder():
    """Stop the forwarder"""
    try:
        with forwarder_lock:
            if not forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'})
            
            if not forwarder.running:
                return jsonify({'success': False, 'error': 'Forwarder is not running'})
            
            success = forwarder.stop()
            
            if success:
                return jsonify({'success': True, 'message': 'Forwarder stopped successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to stop forwarder'})
    
    except Exception as e:
        logger.error(f"Error stopping forwarder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/buffer')
def get_buffer_info():
    """Get buffer information"""
    with forwarder_lock:
        if forwarder:
            with forwarder.buffer_lock:
                buffer_data = []
                for item in list(forwarder.buffer)[:100]:  # Return last 100 items
                    buffer_data.append({
                        'timestamp': item['timestamp'],
                        'size': len(item['data'])
                    })
                
                return jsonify({
                    'total_size': len(forwarder.buffer),
                    'items': buffer_data
                })
        
        return jsonify({'total_size': 0, 'items': []})


@app.route('/api/clear_buffer', methods=['POST'])
def clear_buffer():
    """Clear the buffer"""
    try:
        with forwarder_lock:
            if forwarder:
                with forwarder.buffer_lock:
                    forwarder.buffer.clear()
                # Also remove the persistent buffer file
                forwarder.save_buffer()
                return jsonify({'success': True, 'message': 'Buffer cleared successfully'})
            else:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'})
    except Exception as e:
        logger.error(f"Error clearing buffer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
