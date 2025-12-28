"""
Serial Port to TCP Forwarder with Buffering
Forwards data from serial port to TCP connection with automatic buffering on disconnect
"""
import serial
import socket
import threading
import time
import json
import pickle
import os
import logging
from collections import deque
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SerialToTCPForwarder:
    def __init__(self, config_file='config.json', buffer_file='buffer.pkl'):
        self.config_file = config_file
        self.buffer_file = buffer_file
        self.config = self.load_config()
        
        # Serial port settings
        self.serial_port = None
        self.serial_connected = False
        
        # TCP connection settings
        self.tcp_socket = None
        self.tcp_connected = False
        
        # Buffer for storing data when TCP connection is lost
        self.buffer = deque(maxlen=self.config.get('buffer_size', 10000))
        self.buffer_lock = threading.Lock()
        
        # Load any existing buffered data from disk
        self.load_buffer()
        
        # Status tracking
        self.status = {
            'serial_connected': False,
            'tcp_connected': False,
            'buffer_size': 0,
            'messages_sent': 0,
            'messages_buffered': 0,
            'last_error': None,
            'start_time': datetime.now().isoformat()
        }
        self.status_lock = threading.Lock()
        
        # Control flags
        self.running = False
        self.threads = []
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_file} not found. Using defaults.")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config file: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            'serial_port': '/dev/ttyUSB0',
            'serial_baudrate': 9600,
            'serial_bytesize': 8,
            'serial_parity': 'N',
            'serial_stopbits': 1,
            'serial_timeout': 1,
            'tcp_host': 'localhost',
            'tcp_port': 5000,
            'buffer_size': 10000,
            'reconnect_interval': 5
        }
    
    def save_config(self, new_config):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(new_config, f, indent=4)
            self.config = new_config
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def load_buffer(self):
        """Load buffer from disk if it exists"""
        try:
            if os.path.exists(self.buffer_file):
                with open(self.buffer_file, 'rb') as f:
                    saved_buffer = pickle.load(f)
                    with self.buffer_lock:
                        self.buffer = deque(saved_buffer, maxlen=self.config.get('buffer_size', 10000))
                    logger.info(f"Loaded {len(self.buffer)} buffered messages from disk")
                    if len(self.buffer) > 0:
                        logger.info("Buffer will be sent when TCP connection is established")
        except Exception as e:
            logger.error(f"Error loading buffer from disk: {e}")
            # If there's an error, start with empty buffer
            with self.buffer_lock:
                self.buffer = deque(maxlen=self.config.get('buffer_size', 10000))
    
    def save_buffer(self):
        """Save buffer to disk for persistence across restarts"""
        try:
            with self.buffer_lock:
                buffer_list = list(self.buffer)
            
            # Only save if there's data in the buffer
            if buffer_list:
                with open(self.buffer_file, 'wb') as f:
                    pickle.dump(buffer_list, f)
                logger.debug(f"Saved {len(buffer_list)} buffered messages to disk")
        except Exception as e:
            logger.error(f"Error saving buffer to disk: {e}")
    
    def connect_serial(self):
        """Connect to serial port"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
            
            self.serial_port = serial.Serial(
                port=self.config['serial_port'],
                baudrate=self.config['serial_baudrate'],
                bytesize=self.config['serial_bytesize'],
                parity=parity_map.get(self.config['serial_parity'], serial.PARITY_NONE),
                stopbits=self.config['serial_stopbits'],
                timeout=self.config['serial_timeout']
            )
            
            self.serial_connected = True
            self.update_status('serial_connected', True)
            logger.info(f"Connected to serial port {self.config['serial_port']}")
            return True
        except Exception as e:
            self.serial_connected = False
            self.update_status('serial_connected', False)
            self.update_status('last_error', f"Serial connection error: {str(e)}")
            logger.error(f"Failed to connect to serial port: {e}")
            return False
    
    def connect_tcp(self):
        """Connect to TCP server"""
        try:
            if self.tcp_socket:
                try:
                    self.tcp_socket.close()
                except:
                    pass
            
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(5)
            self.tcp_socket.connect((self.config['tcp_host'], self.config['tcp_port']))
            self.tcp_connected = True
            self.update_status('tcp_connected', True)
            logger.info(f"Connected to TCP server {self.config['tcp_host']}:{self.config['tcp_port']}")
            
            # Send buffered data after reconnection
            self.flush_buffer()
            return True
        except Exception as e:
            self.tcp_connected = False
            self.update_status('tcp_connected', False)
            self.update_status('last_error', f"TCP connection error: {str(e)}")
            logger.error(f"Failed to connect to TCP server: {e}")
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
        """Add data to buffer when TCP connection is lost"""
        with self.buffer_lock:
            self.buffer.append({
                'data': data,
                'timestamp': datetime.now().isoformat()
            })
            self.update_status('messages_buffered', self.status['messages_buffered'] + 1)
            logger.debug(f"Buffered data: {len(data)} bytes. Buffer size: {len(self.buffer)}")
        
        # Save buffer to disk for persistence
        self.save_buffer()
    
    def flush_buffer(self):
        """Send all buffered data when connection is restored"""
        if not self.tcp_connected or not self.tcp_socket:
            return
        
        with self.buffer_lock:
            buffer_size = len(self.buffer)
            if buffer_size == 0:
                return
            
            logger.info(f"Flushing {buffer_size} buffered messages")
            
            while self.buffer:
                item = self.buffer.popleft()
                try:
                    self.tcp_socket.sendall(item['data'])
                    self.update_status('messages_sent', self.status['messages_sent'] + 1)
                except Exception as e:
                    logger.error(f"Error flushing buffer: {e}")
                    # Put it back in buffer
                    self.buffer.appendleft(item)
                    break
            
            logger.info(f"Buffer flush complete. Remaining: {len(self.buffer)}")
            
            # Update persistent storage after flushing
            if len(self.buffer) == 0:
                # Remove buffer file if empty
                try:
                    if os.path.exists(self.buffer_file):
                        os.remove(self.buffer_file)
                        logger.debug("Removed empty buffer file")
                except Exception as e:
                    logger.error(f"Error removing buffer file: {e}")
            else:
                # Save remaining buffer
                self.save_buffer()
    
    def send_data(self, data):
        """Send data via TCP or buffer it if connection is lost"""
        if self.tcp_connected and self.tcp_socket:
            try:
                self.tcp_socket.sendall(data)
                self.update_status('messages_sent', self.status['messages_sent'] + 1)
                return True
            except Exception as e:
                logger.error(f"Error sending data via TCP: {e}")
                self.tcp_connected = False
                self.update_status('tcp_connected', False)
                self.add_to_buffer(data)
                return False
        else:
            self.add_to_buffer(data)
            return False
    
    def serial_reader_thread(self):
        """Thread to read data from serial port and forward to TCP"""
        logger.info("Serial reader thread started")
        
        while self.running:
            if not self.serial_connected:
                if not self.connect_serial():
                    time.sleep(self.config['reconnect_interval'])
                    continue
            
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        logger.debug(f"Received {len(data)} bytes from serial port")
                        self.send_data(data)
                else:
                    time.sleep(0.01)  # Small delay to prevent busy waiting
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self.serial_connected = False
                self.update_status('serial_connected', False)
                self.update_status('last_error', f"Serial read error: {str(e)}")
                time.sleep(self.config['reconnect_interval'])
            except Exception as e:
                logger.error(f"Unexpected error in serial reader: {e}")
                time.sleep(1)
        
        logger.info("Serial reader thread stopped")
    
    def tcp_reconnect_thread(self):
        """Thread to maintain TCP connection"""
        logger.info("TCP reconnect thread started")
        
        while self.running:
            if not self.tcp_connected:
                self.connect_tcp()
                time.sleep(self.config['reconnect_interval'])
            else:
                time.sleep(1)  # Check connection status periodically
        
        logger.info("TCP reconnect thread stopped")
    
    def start(self):
        """Start the forwarder"""
        if self.running:
            logger.warning("Forwarder is already running")
            return False
        
        logger.info("Starting Serial to TCP Forwarder")
        self.running = True
        
        # Start threads
        serial_thread = threading.Thread(target=self.serial_reader_thread, daemon=True)
        tcp_thread = threading.Thread(target=self.tcp_reconnect_thread, daemon=True)
        
        self.threads = [serial_thread, tcp_thread]
        
        for thread in self.threads:
            thread.start()
        
        logger.info("Forwarder started successfully")
        return True
    
    def stop(self):
        """Stop the forwarder"""
        if not self.running:
            logger.warning("Forwarder is not running")
            return False
        
        logger.info("Stopping Serial to TCP Forwarder")
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=2)
        
        # Close connections
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
        
        self.serial_connected = False
        self.tcp_connected = False
        self.update_status('serial_connected', False)
        self.update_status('tcp_connected', False)
        
        logger.info("Forwarder stopped")
        return True


if __name__ == '__main__':
    forwarder = SerialToTCPForwarder()
    forwarder.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        forwarder.stop()
