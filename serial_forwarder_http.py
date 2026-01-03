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
import sqlite3
import os

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
        
        # Persistent SQLite buffer table for retry mechanism
        self.db_path = f'buffer_{port_name}.db'
        self.db_lock = threading.Lock()
        self.retry_interval = 30.0  # 30 seconds
        self.send_success_flag = False
        self._init_database()
        
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
    
    def _init_database(self):
        """Initialize SQLite database for persistent buffer storage"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        data BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
                
                # Log pending messages count
                pending_count = self._get_pending_count()
                if pending_count > 0:
                    logger.info(f"[{self.port_name}] Loaded {pending_count} pending messages from database")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error initializing database: {e}")
    
    def _get_pending_count(self):
        """Get count of pending messages in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM pending_messages')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"[{self.port_name}] Error getting pending count: {e}")
            return 0
    
    def _add_pending_message(self, data_bytes):
        """Add a message to the pending buffer in database"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO pending_messages (timestamp, data) VALUES (?, ?)',
                             (time.time(), data_bytes))
                conn.commit()
                conn.close()
                logger.debug(f"[{self.port_name}] Added message to pending buffer")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error adding pending message: {e}")
    
    def _remove_pending_message(self, message_id):
        """Remove a successfully sent message from database"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM pending_messages WHERE id = ?', (message_id,))
                conn.commit()
                conn.close()
                logger.debug(f"[{self.port_name}] Removed message {message_id} from pending buffer")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error removing pending message: {e}")
    
    def _get_pending_messages(self):
        """Get all pending messages from database"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT id, timestamp, data FROM pending_messages ORDER BY timestamp')
                messages = cursor.fetchall()
                conn.close()
                return messages
        except Exception as e:
            logger.error(f"[{self.port_name}] Error getting pending messages: {e}")
            return []
    
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
            before_size = len(self.buffer)
            self.buffer.extend(data)
            after_size = len(self.buffer)
            self.last_data_time = time.time()
            logger.debug(f"[{self.port_name}] Added {len(data)} bytes to buffer. Buffer: {before_size} -> {after_size} bytes")
            logger.debug(f"[{self.port_name}] First 20 bytes: {data[:20].hex() if len(data) >= 20 else data.hex()}")
    
    def send_buffered_data(self):
        """Send buffered data via HTTP POST"""
        with self.buffer_lock:
            if len(self.buffer) == 0:
                return
            
            # Get data to send
            data_to_send = bytes(self.buffer)
            buffer_size = len(self.buffer)
            self.buffer.clear()
            self.last_data_time = None
        
        # Verify data integrity
        if len(data_to_send) != buffer_size:
            logger.error(f"[{self.port_name}] Data length mismatch! Buffer: {buffer_size}, Converted: {len(data_to_send)}")
        else:
            logger.info(f"[{self.port_name}] Prepared {len(data_to_send)} bytes for sending")
            logger.debug(f"[{self.port_name}] Data checksum: {sum(data_to_send) % 256}")
        
        # Add to pending messages database
        self._add_pending_message(data_to_send)
        
        # Try to send all pending messages
        self._send_pending_messages()
    
    def _send_to_http(self, message_id, data_to_send):
        """Internal method to send data via HTTP POST"""
        # Send via HTTP POST
        try:
            # Send raw binary data with metadata in headers
            headers = {
                'Content-Type': 'application/octet-stream',
                'X-TCP-Host': self.tcp_host,
                'X-TCP-Port': str(self.tcp_port),
                'X-Source-Port': self.port_name,
                'X-Data-Length': str(len(data_to_send)),
                'X-Data-Checksum': str(sum(data_to_send) % 256)
            }
            
            logger.info(f"[{self.port_name}] Sending message ID {message_id}: {len(data_to_send)} bytes to {self.http_url} -> {self.tcp_host}:{self.tcp_port}")
          
            logger.debug(f"[{self.port_name}] Data checksum: {sum(data_to_send) % 256}")
            
            response = requests.post(
                self.http_url,
                data=data_to_send,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                # Success - verify response and remove from database
                try:
                    response_data = response.json()
                    bytes_sent = response_data.get('bytes_sent', 0)
                    if bytes_sent != len(data_to_send):
                        logger.warning(f"[{self.port_name}] Length mismatch! Sent: {len(data_to_send)}, Confirmed: {bytes_sent}")
                    else:
                        logger.info(f"[{self.port_name}] Verified: {bytes_sent} bytes sent successfully")
                except:
                    logger.debug(f"[{self.port_name}] Response: {response.text}")
                
                self._remove_pending_message(message_id)
                
                # Check if all messages sent
                if self._get_pending_count() == 0:
                    self.send_success_flag = True
                
                self.update_status('messages_sent', self.status['messages_sent'] + 1)
                logger.info(f"[{self.port_name}] Successfully sent data. Response: {response.text}")
                return True
            else:
                logger.error(f"[{self.port_name}] HTTP POST failed with status {response.status_code}: {response.text}")
                self.update_status('last_error', f"HTTP POST failed: {response.status_code}")
                self.send_success_flag = False
                return False
                
        except Exception as e:
            logger.error(f"[{self.port_name}] Error sending data via HTTP POST: {e}")
            self.update_status('last_error', f"HTTP POST error: {str(e)}")
            self.send_success_flag = False
            return False
    
    def _send_pending_messages(self):
        """Send all pending messages from database"""
        messages = self._get_pending_messages()
        
        if messages:
            logger.debug(f"[{self.port_name}] Attempting to send {len(messages)} pending messages")
            
            for message_id, timestamp, data in messages:
                self._send_to_http(message_id, data)
    
    def serial_reader_thread(self):
        """Thread to read data from serial port"""
        logger.info(f"[{self.port_name}] Serial reader thread started")
        reconnect_interval = self.port_config.get('reconnect_interval', 5)
        
        while self.running:
            if not self.running:
                break
                
            if not self.serial_connected:
                if not self.connect_serial():
                    # Sleep in small increments to allow quick exit
                    for _ in range(int(reconnect_interval * 10)):
                        if not self.running:
                            break
                        time.sleep(0.1)
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
                    # Sleep in small increments to allow quick exit
                    for _ in range(int(reconnect_interval * 10)):
                        if not self.running:
                            break
                        time.sleep(0.1)
            except Exception as e:
                if self.running:
                    logger.error(f"[{self.port_name}] Unexpected error in serial reader: {e}")
                    time.sleep(1)
        
        logger.info(f"[{self.port_name}] Serial reader thread stopped")
    
    def buffer_timeout_thread(self):
        """Thread to monitor buffer timeout and send data after 5 seconds of inactivity"""
        logger.info(f"[{self.port_name}] Buffer timeout thread started")
        
        while self.running:
            if not self.running:
                break
                
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
    
    def retry_pending_messages_thread(self):
        """Thread to retry sending pending messages every 30 seconds"""
        logger.info(f"[{self.port_name}] Retry pending messages thread started")
        
        while self.running:
            # Sleep in small increments to allow quick exit
            for _ in range(int(self.retry_interval * 2)):
                if not self.running:
                    break
                time.sleep(0.5)
            
            if not self.running:
                break
                
            try:
                
                messages = self._get_pending_messages()
                
                if messages:
                    logger.info(f"[{self.port_name}] Retrying {len(messages)} pending messages")
                    
                    for message_id, timestamp, data in messages:
                        age = time.time() - timestamp
                        logger.info(f"[{self.port_name}] Retrying message ID {message_id} ({len(data)} bytes, age: {age:.1f}s)")
                        self._send_to_http(message_id, data)
                
            except Exception as e:
                if self.running:
                    logger.error(f"[{self.port_name}] Error in retry thread: {e}")
                    time.sleep(1)
        
        logger.info(f"[{self.port_name}] Retry pending messages thread stopped")
    
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
        retry_thread = threading.Thread(target=self.retry_pending_messages_thread, daemon=True)
        
        self.threads = [serial_thread, timeout_thread, retry_thread]
        
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
        
        # Set running flag to False FIRST
        self.running = False
        
        # Close serial port immediately to stop reading
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                logger.info(f"[{self.port_name}] Serial port closed")
            except Exception as e:
                logger.error(f"[{self.port_name}] Error closing serial port: {e}")
        
        # Wait for all threads to finish with reduced timeout
        logger.debug(f"[{self.port_name}] Waiting for {len(self.threads)} threads to finish")
        for i, thread in enumerate(self.threads, 1):
            if thread.is_alive():
                logger.debug(f"[{self.port_name}] Waiting for thread {i}/{len(self.threads)}")
                try:
                    thread.join(timeout=2)  # Reduced timeout from 5 to 2 seconds
                    if thread.is_alive():
                        logger.warning(f"[{self.port_name}] Thread {i} did not stop within timeout - continuing anyway")
                except KeyboardInterrupt:
                    logger.warning(f"[{self.port_name}] Interrupted while waiting for thread {i}, forcing exit")
                    break
        
        logger.info(f"[{self.port_name}] Thread cleanup completed")
        
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
        self.running = False
        
        # Stop all forwarders in parallel using threads for faster shutdown
        stop_threads = []
        for port_name, forwarder in self.forwarders.items():
            thread = threading.Thread(target=forwarder.stop, daemon=True)
            thread.start()
            stop_threads.append((port_name, thread))
        
        # Wait for all stop operations to complete with timeout
        for port_name, thread in stop_threads:
            thread.join(timeout=3)
            if thread.is_alive():
                logger.warning(f"Stop operation for {port_name} did not complete within timeout")
        
        logger.info("MultiPortHTTPForwarder stopped")
        return True
    
    def get_status(self):
        """Get status of all forwarders"""
        status = {}
        for port_name, forwarder in self.forwarders.items():
            status[port_name] = forwarder.get_status()
        return status
    
    def get_forwarder(self, port_name):
        """Get a specific forwarder by port name"""
        return self.forwarders.get(port_name)


def main():
    """Main function"""
    # Load configuration
    import sys
    config_file = 'config.json' if len(sys.argv) < 2 else sys.argv[1]
    
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
        try:
            forwarder.stop()
            logger.info("Forwarder stopped gracefully")
        except KeyboardInterrupt:
            logger.warning("Interrupted during cleanup, forcing exit")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == '__main__':
    main()
