"""
Serial Port to HTTP POST Forwarder with 5-second buffering
Reads serial data, buffers it, and sends via HTTP POST after 5 seconds of inactivity
"""
import sys
import serial
import threading
import time
import json
import logging
from datetime import datetime
import requests

# Check Python version - 3.8 or 3.9
if sys.version_info < (3, 8) or sys.version_info >= (3, 10):
    print("Error: Python 3.8 or 3.9 is required")
    print(f"Current version: {sys.version}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SinglePortHTTPForwarder:
    """Handles forwarding for a single serial port to HTTP POST endpoint"""
    
    def __init__(self, port_name, port_config):
        self.port_name = port_name
        self.port_config = port_config
        
        # Serial port settings
        self.serial_port = None
        self.serial_connected = False
        
        # HTTP settings
        self.http_url = port_config.get('http_url', 'http://localhost:5000/forward')
        self.tcp_host = port_config.get('tcp_host', 'localhost')
        self.tcp_port = port_config.get('tcp_port', 8090)
        
        # Buffer for storing data with 5-second timeout
        self.buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.last_data_time = None
        self.buffer_timeout = 5.0  # 5 seconds
        
        # Status tracking
        self.status = {
            'port_name': port_name,
            'serial_connected': False,
            'http_url': self.http_url,
            'tcp_host': self.tcp_host,
            'tcp_port': self.tcp_port,
            'buffer_size': 0,
            'messages_sent': 0,
            'last_error': None,
            'start_time': datetime.now().isoformat()
        }
        self.status_lock = threading.Lock()
        
        # Control flags
        self.running = False
        self.threads = []
    
    def connect_serial(self):
        """Connect to serial port"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
            
            self.serial_port = serial.Serial(
                port=self.port_config['serial_port'],
                baudrate=self.port_config['serial_baudrate'],
                bytesize=self.port_config['serial_bytesize'],
                parity=parity_map.get(self.port_config['serial_parity'], serial.PARITY_NONE),
                stopbits=self.port_config['serial_stopbits'],
                timeout=self.port_config['serial_timeout'],
                xonxoff=self.port_config.get('serial_xonxoff', True),
                rtscts=self.port_config.get('serial_rtscts', False)
            )
            
            self.serial_connected = True
            self.update_status('serial_connected', True)
            logger.info(f"[{self.port_name}] Connected to serial port {self.port_config['serial_port']}")
            return True
        except Exception as e:
            self.serial_connected = False
            self.update_status('serial_connected', False)
            self.update_status('last_error', f"Serial connection error: {str(e)}")
            logger.error(f"[{self.port_name}] Failed to connect to serial port: {e}")
            return False
    
    def update_status(self, key, value):
        """Thread-safe status update"""
        with self.status_lock:
            self.status[key] = value
    
    def get_status(self):
        """Get current status"""
        with self.status_lock:
            with self.buffer_lock:
                self.status['buffer_size'] = len(self.buffer)
            return self.status.copy()
    
    def add_to_buffer(self, data):
        """Add data to buffer and update timestamp"""
        with self.buffer_lock:
            self.buffer.extend(data)
            self.last_data_time = time.time()
            logger.debug(f"[{self.port_name}] Added {len(data)} bytes to buffer. Total: {len(self.buffer)} bytes")
    
    def send_buffered_data(self):
        """Send buffered data via HTTP POST"""
        with self.buffer_lock:
            if len(self.buffer) == 0:
                return
            
            # Get data to send
            data_to_send = bytes(self.buffer)
            self.buffer.clear()
            self.last_data_time = None
        
        # Send via HTTP POST
        try:
            payload = {
                'datahost': self.tcp_host,
                'tcp_port': self.tcp_port,
                'source_port': self.port_name
            }
            
            logger.info(f"[{self.port_name}] Sending {len(data_to_send)} bytes to {self.http_url} -> {self.tcp_host}:{self.tcp_port}")
            
            response = requests.post(
                self.http_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.update_status('messages_sent', self.status['messages_sent'] + 1)
                logger.info(f"[{self.port_name}] Successfully sent data. Response: {response.text}")
            else:
                logger.error(f"[{self.port_name}] HTTP POST failed with status {response.status_code}: {response.text}")
                self.update_status('last_error', f"HTTP POST failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"[{self.port_name}] Error sending data via HTTP POST: {e}")
            self.update_status('last_error', f"HTTP POST error: {str(e)}")
    
    def serial_reader_thread(self):
        """Thread to read data from serial port"""
        logger.info(f"[{self.port_name}] Serial reader thread started")
        reconnect_interval = self.port_config.get('reconnect_interval', 5)
        
        while self.running:
            if not self.serial_connected:
                if not self.connect_serial():
                    if self.running:
                        time.sleep(reconnect_interval)
                    continue
            
            try:
                if not self.running:
                    break
                
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data and self.running:
                        logger.debug(f"[{self.port_name}] Received {len(data)} bytes from serial port")
                        self.add_to_buffer(data)
                else:
                    time.sleep(0.1)
            except serial.SerialException as e:
                if self.running:
                    logger.error(f"[{self.port_name}] Serial read error: {e}")
                    self.serial_connected = False
                    self.update_status('serial_connected', False)
                    self.update_status('last_error', f"Serial read error: {str(e)}")
                    time.sleep(reconnect_interval)
            except Exception as e:
                if self.running:
                    logger.error(f"[{self.port_name}] Unexpected error in serial reader: {e}")
                    time.sleep(1)
        
        logger.info(f"[{self.port_name}] Serial reader thread stopped")
    
    def buffer_timeout_thread(self):
        """Thread to monitor buffer timeout and send data after 5 seconds of inactivity"""
        logger.info(f"[{self.port_name}] Buffer timeout thread started")
        
        while self.running:
            try:
                current_time = time.time()
                
                with self.buffer_lock:
                    if (self.last_data_time is not None and 
                        len(self.buffer) > 0 and
                        (current_time - self.last_data_time) >= self.buffer_timeout):
                        # Release lock before sending
                        should_send = True
                    else:
                        should_send = False
                
                if should_send:
                    logger.info(f"[{self.port_name}] Buffer timeout reached, sending data")
                    self.send_buffered_data()
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                if self.running:
                    logger.error(f"[{self.port_name}] Error in buffer timeout thread: {e}")
                    time.sleep(1)
        
        logger.info(f"[{self.port_name}] Buffer timeout thread stopped")
    
    def start(self):
        """Start the forwarder for this port"""
        if self.running:
            logger.warning(f"[{self.port_name}] Forwarder is already running")
            return False
        
        logger.info(f"[{self.port_name}] Starting HTTP forwarder")
        self.running = True
        
        # Start threads
        serial_thread = threading.Thread(target=self.serial_reader_thread, daemon=True)
        timeout_thread = threading.Thread(target=self.buffer_timeout_thread, daemon=True)
        
        self.threads = [serial_thread, timeout_thread]
        
        for thread in self.threads:
            thread.start()
        
        logger.info(f"[{self.port_name}] HTTP forwarder started successfully")
        return True
    
    def stop(self):
        """Stop the forwarder for this port"""
        if not self.running:
            logger.warning(f"[{self.port_name}] Forwarder is not running")
            return False
        
        logger.info(f"[{self.port_name}] Stopping HTTP forwarder")
        
        # Set running flag to False
        self.running = False
        
        # Wait for all threads to finish
        logger.debug(f"[{self.port_name}] Waiting for {len(self.threads)} threads to finish")
        for i, thread in enumerate(self.threads, 1):
            if thread.is_alive():
                logger.debug(f"[{self.port_name}] Waiting for thread {i}/{len(self.threads)}")
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"[{self.port_name}] Thread {i} did not stop within timeout")
        
        logger.info(f"[{self.port_name}] All threads stopped")
        
        # Send any remaining buffered data
        with self.buffer_lock:
            if len(self.buffer) > 0:
                logger.info(f"[{self.port_name}] Sending remaining {len(self.buffer)} bytes before shutdown")
        
        self.send_buffered_data()
        
        # Close serial port
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                logger.info(f"[{self.port_name}] Serial port closed")
            except Exception as e:
                logger.error(f"[{self.port_name}] Error closing serial port: {e}")
        
        self.serial_connected = False
        self.update_status('serial_connected', False)
        
        logger.info(f"[{self.port_name}] HTTP forwarder stopped")
        return True


class MultiPortHTTPForwarder:
    """Manages multiple serial port HTTP forwarders"""
    
    def __init__(self, config):
        self.config = config
        self.forwarders = {}
        self.running = False
    
    def start(self):
        """Start all forwarders"""
        if self.running:
            logger.warning("MultiPortHTTPForwarder is already running")
            return False
        
        logger.info("Starting MultiPortHTTPForwarder")
        self.running = True
        
        for port_config in self.config.get('ports', []):
            port_name = port_config['name']
            forwarder = SinglePortHTTPForwarder(port_name, port_config)
            self.forwarders[port_name] = forwarder
            forwarder.start()
        
        logger.info(f"MultiPortHTTPForwarder started with {len(self.forwarders)} ports")
        return True
    
    def stop(self):
        """Stop all forwarders"""
        if not self.running:
            logger.warning("MultiPortHTTPForwarder is not running")
            return False
        
        logger.info("Stopping MultiPortHTTPForwarder")
        
        for port_name, forwarder in self.forwarders.items():
            forwarder.stop()
        
        self.running = False
        logger.info("MultiPortHTTPForwarder stopped")
        return True
    
    def get_status(self):
        """Get status of all forwarders"""
        status = {}
        for port_name, forwarder in self.forwarders.items():
            status[port_name] = forwarder.get_status()
        return status


def main():
    """Main function"""
    # Load configuration
    import sys
    config_file = 'config_http.json' if len(sys.argv) < 2 else sys.argv[1]
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded configuration from {config_file}")
    except Exception as e:
        logger.error(f"Error loading {config_file}: {e}")
        sys.exit(1)
    
    # Create and start forwarder
    forwarder = MultiPortHTTPForwarder(config)
    
    try:
        forwarder.start()
        logger.info("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping...")
        forwarder.stop()
        logger.info("Forwarder stopped gracefully")


if __name__ == '__main__':
    main()
