"""
TCP Forwarder Server
Receives HTTP POST requests with data and TCP port, then forwards the data to the specified TCP port
"""
import sys
import socket
import logging
from flask import Flask, request, jsonify
import threading

# Check Python version - 3.8 only
if sys.version_info < (3, 8) or sys.version_info >= (3, 10):
    print("Error: Python 3.8 or 3.9 is required")
    print(f"Current version: {sys.version}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)


class TCPForwarder:
    """Handles TCP connection and data forwarding"""
    
    def __init__(self, host, port, data, timeout=5):
        self.host = host
        self.port = port
        self.data = data
        self.timeout = timeout
        self.result = None
        self.error = None
    
    def send(self):
        """Send data to TCP port"""
        try:
            logger.info(f"Connecting to {self.host}:{self.port}")
            
            # Create TCP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # Connect to target
            sock.connect((self.host, self.port))
            logger.info(f"Connected to {self.host}:{self.port}")
            
            # Send data
            sock.sendall(self.data)
            logger.info(f"Sent {len(self.data)} bytes to {self.host}:{self.port}")
            
            # Close connection
            sock.close()
            
            self.result = f"Successfully sent {len(self.data)} bytes to {self.host}:{self.port}"
            return True
            
        except socket.timeout:
            self.error = f"Connection timeout to {self.host}:{self.port}"
            logger.error(self.error)
            return False
        except ConnectionRefusedError:
            self.error = f"Connection refused by {self.host}:{self.port}"
            logger.error(self.error)
            return False
        except Exception as e:
            self.error = f"Error sending data to {self.host}:{self.port}: {str(e)}"
            logger.error(self.error)
            return False


@app.route('/forward', methods=['POST'])
def forward_data():
    """
    Receive POST request with data and TCP port, then forward to TCP
    
    Expected JSON payload:
    {
        "data": "hex_encoded_string",
        "tcp_port": 8090,
        "tcp_host": "192.168.21.18" (optional, defaults to localhost)
        "source_port": "port1" (optional, for logging)
    }
    """
    try:
        # Get JSON data
        json_data = request.get_json()
        
        if not json_data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract parameters
        hex_data = json_data.get('data')
        tcp_port = json_data.get('tcp_port')
        tcp_host = json_data.get('tcp_host', 'localhost')
        source_port = json_data.get('source_port', 'unknown')
        
        # Validate required fields
        if not hex_data:
            return jsonify({'error': 'Missing "data" field'}), 400
        
        if not tcp_port:
            return jsonify({'error': 'Missing "tcp_port" field'}), 400
        
        # Convert hex string to bytes
        try:
            data_bytes = bytes.fromhex(hex_data)
        except ValueError as e:
            return jsonify({'error': f'Invalid hex data: {str(e)}'}), 400
        
        logger.info(f"Received request from {source_port}: {len(data_bytes)} bytes to {tcp_host}:{tcp_port}")
        
        # Forward to TCP
        forwarder = TCPForwarder(tcp_host, tcp_port, data_bytes)
        success = forwarder.send()
        
        if success:
            return jsonify({
                'success': True,
                'message': forwarder.result,
                'bytes_sent': len(data_bytes),
                'target': f"{tcp_host}:{tcp_port}"
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': forwarder.error,
                'target': f"{tcp_host}:{tcp_port}"
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/status', methods=['GET'])
def status():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'TCP Forwarder Server',
        'version': '1.0'
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with information"""
    return jsonify({
        'service': 'TCP Forwarder Server',
        'version': '1.0',
        'endpoints': {
            '/forward': 'POST - Forward data to TCP port',
            '/status': 'GET - Service status',
            '/': 'GET - This information'
        },
        'usage': {
            'url': '/forward',
            'method': 'POST',
            'content_type': 'application/json',
            'body': {
                'data': 'hex_encoded_string (required)',
                'tcp_port': 'target_port_number (required)',
                'tcp_host': 'target_host (optional, default: localhost)',
                'source_port': 'source_identifier (optional)'
            }
        }
    }), 200


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TCP Forwarder Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting TCP Forwarder Server on {args.host}:{args.port}")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
