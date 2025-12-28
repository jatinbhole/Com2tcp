"""
Flask Web Service for Serial to TCP Forwarder Configuration and Monitoring
Supports multiple serial ports with independent configuration and control
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import threading
import logging
from serial_forwarder import MultiPortForwarder

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# Initialize forwarder
multi_forwarder = None
forwarder_lock = threading.Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index_multi.html')


@app.route('/api/status')
def get_status():
    """Get status of all forwarders"""
    with forwarder_lock:
        if multi_forwarder:
            return jsonify(multi_forwarder.get_status())
        else:
            return jsonify({
                'timestamp': '',
                'forwarders': {}
            })


@app.route('/api/status/<port_name>')
def get_port_status(port_name):
    """Get status of a specific port"""
    with forwarder_lock:
        if multi_forwarder:
            forwarder = multi_forwarder.get_forwarder(port_name)
            if forwarder:
                return jsonify(forwarder.get_status())
            else:
                return jsonify({'error': 'Port not found'}), 404
        else:
            return jsonify({'error': 'Forwarder not initialized'}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    with forwarder_lock:
        if multi_forwarder:
            return jsonify(multi_forwarder.config)
        else:
            # Return default config
            temp_forwarder = MultiPortForwarder()
            return jsonify(temp_forwarder.get_default_config())


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.get_json()
        
        # Validate configuration
        if 'ports' not in new_config:
            return jsonify({'success': False, 'error': 'Missing ports configuration'}), 400
        
        ports = new_config.get('ports', [])
        if not ports:
            return jsonify({'success': False, 'error': 'At least one port must be configured'}), 400
        
        # Validate each port
        for port in ports:
            required_fields = ['name', 'serial_port', 'serial_baudrate', 'tcp_host', 'tcp_port']
            for field in required_fields:
                if field not in port:
                    return jsonify({'success': False, 'error': f'Missing required field in port: {field}'}), 400
        
        with forwarder_lock:
            global multi_forwarder
            
            # Stop existing forwarder if running
            was_running = False
            if multi_forwarder:
                # Get running status before stopping
                for forwarder in multi_forwarder.forwarders.values():
                    if forwarder.running:
                        was_running = True
                        break
                multi_forwarder.stop()
            
            # Create new forwarder with updated config
            multi_forwarder = MultiPortForwarder()
            multi_forwarder.save_config(new_config)
            
            # Restart if it was running
            if was_running:
                multi_forwarder.start()
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_forwarder():
    """Start all forwarders"""
    try:
        with forwarder_lock:
            global multi_forwarder
            
            if not multi_forwarder:
                multi_forwarder = MultiPortForwarder()
            
            success = multi_forwarder.start()
            
            if success:
                return jsonify({'success': True, 'message': f'Started {len(multi_forwarder.forwarders)} forwarders'})
            else:
                return jsonify({'success': False, 'error': 'Failed to start forwarders'})
    
    except Exception as e:
        logger.error(f"Error starting forwarders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start/<port_name>', methods=['POST'])
def start_port(port_name):
    """Start a specific port forwarder"""
    try:
        with forwarder_lock:
            if not multi_forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'}), 500
            
            forwarder = multi_forwarder.get_forwarder(port_name)
            if not forwarder:
                return jsonify({'success': False, 'error': f'Port {port_name} not found'}), 404
            
            if forwarder.running:
                return jsonify({'success': False, 'error': f'Port {port_name} is already running'}), 400
            
            success = forwarder.start()
            
            if success:
                return jsonify({'success': True, 'message': f'Port {port_name} started successfully'})
            else:
                return jsonify({'success': False, 'error': f'Failed to start port {port_name}'})
    
    except Exception as e:
        logger.error(f"Error starting port {port_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_forwarder():
    """Stop all forwarders"""
    try:
        with forwarder_lock:
            if not multi_forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'}), 500
            
            success = multi_forwarder.stop()
            
            if success:
                return jsonify({'success': True, 'message': 'All forwarders stopped successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to stop forwarders'})
    
    except Exception as e:
        logger.error(f"Error stopping forwarders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stop/<port_name>', methods=['POST'])
def stop_port(port_name):
    """Stop a specific port forwarder"""
    try:
        with forwarder_lock:
            if not multi_forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'}), 500
            
            forwarder = multi_forwarder.get_forwarder(port_name)
            if not forwarder:
                return jsonify({'success': False, 'error': f'Port {port_name} not found'}), 404
            
            if not forwarder.running:
                return jsonify({'success': False, 'error': f'Port {port_name} is not running'}), 400
            
            success = forwarder.stop()
            
            if success:
                return jsonify({'success': True, 'message': f'Port {port_name} stopped successfully'})
            else:
                return jsonify({'success': False, 'error': f'Failed to stop port {port_name}'})
    
    except Exception as e:
        logger.error(f"Error stopping port {port_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/buffer')
def get_buffer_info():
    """Get buffer information for all ports"""
    with forwarder_lock:
        if multi_forwarder:
            buffer_info = {}
            for port_name, forwarder in multi_forwarder.forwarders.items():
                with forwarder.buffer_lock:
                    buffer_data = []
                    for item in list(forwarder.buffer)[:100]:  # Return last 100 items
                        buffer_data.append({
                            'timestamp': item['timestamp'],
                            'size': len(item['data'])
                        })
                    
                    buffer_info[port_name] = {
                        'total_size': len(forwarder.buffer),
                        'items': buffer_data
                    }
            
            return jsonify(buffer_info)
        
        return jsonify({})


@app.route('/api/buffer/<port_name>')
def get_port_buffer_info(port_name):
    """Get buffer information for a specific port"""
    with forwarder_lock:
        if not multi_forwarder:
            return jsonify({'error': 'Forwarder not initialized'}), 500
        
        forwarder = multi_forwarder.get_forwarder(port_name)
        if not forwarder:
            return jsonify({'error': 'Port not found'}), 404
        
        with forwarder.buffer_lock:
            buffer_data = []
            for item in list(forwarder.buffer)[:100]:  # Return last 100 items
                buffer_data.append({
                    'timestamp': item['timestamp'],
                    'size': len(item['data'])
                })
            
            return jsonify({
                'port_name': port_name,
                'total_size': len(forwarder.buffer),
                'items': buffer_data
            })


@app.route('/api/clear_buffer', methods=['POST'])
def clear_buffer():
    """Clear buffer for all ports"""
    try:
        with forwarder_lock:
            if not multi_forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'}), 500
            
            cleared_count = 0
            for port_name, forwarder in multi_forwarder.forwarders.items():
                with forwarder.buffer_lock:
                    forwarder.buffer.clear()
                forwarder.save_buffer()
                cleared_count += 1
            
            return jsonify({'success': True, 'message': f'Buffer cleared for {cleared_count} ports'})
    except Exception as e:
        logger.error(f"Error clearing buffer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clear_buffer/<port_name>', methods=['POST'])
def clear_port_buffer(port_name):
    """Clear buffer for a specific port"""
    try:
        with forwarder_lock:
            if not multi_forwarder:
                return jsonify({'success': False, 'error': 'Forwarder not initialized'}), 500
            
            forwarder = multi_forwarder.get_forwarder(port_name)
            if not forwarder:
                return jsonify({'success': False, 'error': f'Port {port_name} not found'}), 404
            
            with forwarder.buffer_lock:
                forwarder.buffer.clear()
            forwarder.save_buffer()
            
            return jsonify({'success': True, 'message': f'Buffer cleared for port {port_name}'})
    except Exception as e:
        logger.error(f"Error clearing buffer for port {port_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize multi-forwarder on startup
    with forwarder_lock:
        multi_forwarder = MultiPortForwarder()
    
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
