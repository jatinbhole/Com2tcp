# updated code 
"""
Serial Port to TCP Forwarder with Buffering - FIXED VERSION
Forwards data from serial ports to TCP connections with automatic buffering on disconnect
Supports multiple serial ports with independent TCP forwarding
Uses SQLite for persistent buffer storage

Requirements:
- Python 3.8 only

FIXES:
1. Proper buffer flushing - only mark as sent after successful TCP send
2. Atomic database operations with transactions
3. Race condition fixes in stop() - save buffer AFTER threads stop
4. Proper thread coordination during shutdown
5. No data loss on Ctrl+C or crash
"""
import sys
import serial
import socket
import threading
import time
import json
import sqlite3
import os
import logging
from collections import deque
from datetime import datetime

# Check Python version - 3.8 only
if sys.version_info < (3, 8) or sys.version_info >= (3, 9):
    print("Error: Python 3.8 only is required")
    print(f"Current version: {sys.version}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SinglePortForwarder:
    """Handles forwarding for a single serial port to TCP connection"""
    
    def __init__(self, port_name, port_config, buffer_dir='buffers'):
        self.port_name = port_name
        self.port_config = port_config
        self.buffer_dir = buffer_dir
        self.db_file = os.path.join(buffer_dir, f'buffer_{port_name}.db')
        
        # Serial port settings
        self.serial_port = None
        self.serial_connected = False
        
        # TCP connection settings
        self.tcp_socket = None
        self.tcp_connected = False
        
        # Serial data accumulation buffer
        self.serial_accumulator = bytearray()
        self.serial_accumulator_lock = threading.Lock()
        self.last_serial_data_time = None
        
        # Buffer for storing data when TCP connection is lost
        buffer_size = port_config.get('buffer_size', 10000)
        self.buffer = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()
        self.db_lock = threading.Lock()
        
        # Create buffer directory if it doesn't exist
        os.makedirs(buffer_dir, exist_ok=True)
        
        # Initialize database
        self.init_db()
        
        # Load any existing buffered data from disk
        self.load_buffer()
        
        # Load any pending accumulated serial data
        self.load_pending_data()
        
        # Status tracking
        self.status = {
            'port_name': port_name,
            'serial_connected': False,
            'tcp_connected': False,
            'tcp_state': 'disconnected', 
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
    
    def init_db(self):
        """Initialize SQLite database for buffer storage"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS buffer (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data BLOB NOT NULL,
                        timestamp TEXT NOT NULL,
                        sent INTEGER DEFAULT 0,
                        sent_timestamp TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
            logger.debug(f"[{self.port_name}] Database initialized at {self.db_file}")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error initializing database: {e}")
    
    def load_buffer(self):
        """Load buffer from SQLite database"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                # Handle old schema without sent columns by using SELECT with defaults
                try:
                    cursor.execute('SELECT data, timestamp, sent, sent_timestamp FROM buffer WHERE timestamp != "PENDING_ACCUMULATOR" ORDER BY id ASC')
                except sqlite3.OperationalError:
                    # Fallback for old schema
                    cursor.execute('SELECT data, timestamp FROM buffer WHERE timestamp != "PENDING_ACCUMULATOR" ORDER BY id ASC')
                rows = cursor.fetchall()
                conn.close()
            
            if rows:
                with self.buffer_lock:
                    self.buffer.clear()
                    for row in rows:
                        if len(row) == 4:
                            data, timestamp, sent, sent_timestamp = row
                        else:
                            data, timestamp = row
                            sent = 0
                            sent_timestamp = None
                        self.buffer.append({
                            'data': data,
                            'timestamp': timestamp,
                            'sent': sent,
                            'sent_timestamp': sent_timestamp
                        })
                
                unsent_count = len([item for item in self.buffer if item.get('sent') == 0])
                logger.info(f"[{self.port_name}] Loaded {len(self.buffer)} buffered messages from database ({unsent_count} unsent)")
                if unsent_count > 0:
                    logger.info(f"[{self.port_name}] {unsent_count} unsent messages will be sent when TCP connection is established")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error loading buffer from database: {e}")
            # If there's an error, start with empty buffer
            with self.buffer_lock:
                self.buffer = deque(maxlen=self.port_config.get('buffer_size', 10000))
    
    def load_pending_data(self):
        """Load pending accumulated serial data from buffer table"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                # Use special timestamp marker to identify pending accumulator data
                cursor.execute('SELECT data, timestamp FROM buffer WHERE timestamp = "PENDING_ACCUMULATOR"')
                row = cursor.fetchone()
                conn.close()
            
            if row:
                data, _ = row
                with self.serial_accumulator_lock:
                    self.serial_accumulator = bytearray(data)
                    self.last_serial_data_time = time.time()  # Reset timer to send soon
                logger.info(f"[{self.port_name}] Restored {len(data)} bytes of pending accumulated data from database")
                logger.info(f"[{self.port_name}] Data will be sent after {self.port_config.get('send_delay', 5)}s delay or immediately if TCP is available")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error loading pending data from database: {e}")
    
    def save_pending_data(self):
        """Save or clear pending accumulated serial data in buffer table
        
        This is used for data that's being accumulated during the 5-second wait.
        Only deletes from DB after successful TCP send.
        """
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                # Always delete existing pending entry first
                cursor.execute('DELETE FROM buffer WHERE timestamp = "PENDING_ACCUMULATOR"')
                
                # Check if there's data to save
                with self.serial_accumulator_lock:
                    if self.serial_accumulator:
                        data = bytes(self.serial_accumulator)
                    else:
                        data = None
                
                # Insert new pending data if exists (data still accumulating)
                if data:
                    cursor.execute('''
                        INSERT INTO buffer (data, timestamp, sent) 
                        VALUES (?, "PENDING_ACCUMULATOR", 0)
                    ''', (data,))
                    logger.debug(f"[{self.port_name}] Saved {len(data)} bytes of pending accumulated data to database")
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            logger.error(f"[{self.port_name}] Error saving pending data to database: {e}")
    
    def save_buffer(self):
        """Save current buffer to SQLite database with transaction safety
        
        BUFFER TABLE USE CASES:
        1. Regular entries (timestamp != PENDING_ACCUMULATOR):
           - Data that FAILED to send via TCP because connection was down
           - Marked with sent=0 (unsent) or sent=1 (successfully sent)
           - These are retried when TCP reconnects (flush_buffer)
        
        2. PENDING_ACCUMULATOR entry (timestamp = PENDING_ACCUMULATOR):
           - Data currently being accumulated during 5-second send delay
           - Saved every 2 seconds for crash recovery
           - Only deleted AFTER successful TCP send
           - If service restarts, this data is restored and sent
        """
        try:
            with self.buffer_lock:
                buffer_list = list(self.buffer)
            
            with self.db_lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                try:
                    # Use transaction for atomicity
                    cursor.execute('BEGIN TRANSACTION')
                    
                    # Clear existing buffer but keep PENDING_ACCUMULATOR
                    cursor.execute('DELETE FROM buffer WHERE timestamp != "PENDING_ACCUMULATOR"')
                    
                    # Insert all buffer items
                    for item in buffer_list:
                        cursor.execute(
                            'INSERT INTO buffer (data, timestamp, sent, sent_timestamp) VALUES (?, ?, ?, ?)',
                            (item['data'], item['timestamp'], item.get('sent', 0), item.get('sent_timestamp', None))
                        )
                    
                    cursor.execute('COMMIT')
                    logger.debug(f"[{self.port_name}] Saved {len(buffer_list)} buffered messages to database")
                    
                except Exception as e:
                    cursor.execute('ROLLBACK')
                    logger.error(f"[{self.port_name}] Error in save_buffer transaction, rolled back: {e}")
                    raise
                
                finally:
                    conn.close()
            
        except Exception as e:
            logger.error(f"[{self.port_name}] CRITICAL: Error saving buffer to database: {e}")
    
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
    
   

    def connect_tcp(self):
        """Connect to TCP server (with proper state handling)"""
        try:
            #  Mark as CONNECTING immediately (important for UI)
            self.update_status('tcp_state', 'connecting')
            self.update_status('tcp_connected', False)

            if self.tcp_socket:
                try:
                    self.tcp_socket.close()
                except:
                    pass

            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(5)
            
            # Enable TCP keepalive for faster disconnect detection
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # Windows-specific keepalive settings (1s idle, 500ms interval)
            try:
                self.tcp_socket.ioctl(
                    socket.SIO_KEEPALIVE_VALS,
                    (1, 1000, 500)  # enable, 1000ms idle time, 500ms probe interval
                )
            except (OSError, AttributeError):
                # Not Windows or ioctl not supported, use standard keepalive
                pass

            self.tcp_socket.connect(
                (self.port_config['tcp_host'], self.port_config['tcp_port'])
            )

            #  Connected successfully
            self.tcp_connected = True
            self.update_status('tcp_connected', True)
            self.update_status('tcp_state', 'connected')

            logger.info(
                f"[{self.port_name}] Connected to TCP server "
                f"{self.port_config['tcp_host']}:{self.port_config['tcp_port']}"
            )

            #  Flush buffered data AFTER successful connect
            self.flush_buffer()
            return True

        except Exception as e:
            #  Connection failed
            self.tcp_connected = False
            self.update_status('tcp_connected', False)
            self.update_status('tcp_state', 'disconnected')
            self.update_status('last_error', f"TCP connection error: {str(e)}")

            logger.error(
                f"[{self.port_name}] Failed to connect to TCP server: {e}"
            )

            # Ensure socket is fully cleaned up
            try:
                if self.tcp_socket:
                    self.tcp_socket.close()
            except:
                pass

            self.tcp_socket = None
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
                'timestamp': datetime.now().isoformat(),
                'sent': 0,
                'sent_timestamp': None
            })
            self.update_status('messages_buffered', self.status['messages_buffered'] + 1)
            buffer_size = len(self.buffer)
            logger.debug(f"[{self.port_name}] Buffered data: {len(data)} bytes. Buffer size: {buffer_size}")
            
            # Warn if buffer is getting full (80% capacity)
            max_size = self.buffer.maxlen
            if max_size and buffer_size > max_size * 0.8:
                logger.warning(f"[{self.port_name}] Buffer is {(buffer_size/max_size)*100:.1f}% full ({buffer_size}/{max_size})")
        
        # Save buffer to disk for persistence
        try:
            self.save_buffer()
        except Exception as e:
            logger.error(f"[{self.port_name}] CRITICAL: Failed to save buffer to disk: {e}")
    
    def cleanup_old_buffer(self):
        """Remove sent messages older than 1 month from buffer"""
        cutoff_time = datetime.now()
        try:
            with self.buffer_lock:
                # Filter out old sent messages (older than 1 month)
                items_to_keep = []
                items_removed = 0
                
                for item in self.buffer:
                    if item.get('sent') == 1 and item.get('sent_timestamp'):
                        try:
                            sent_time = datetime.fromisoformat(item['sent_timestamp'])
                            age_seconds = (cutoff_time - sent_time).total_seconds()
                            if age_seconds > 2592000:  # 1 month = 30 days = 2,592,000 seconds
                                items_removed += 1
                                age_days = age_seconds / (24 * 60 * 60)
                                logger.debug(f"[{self.port_name}] Removing sent message older than 1 month (age: {age_days:.1f} days)")
                                continue
                        except (ValueError, TypeError) as e:
                            logger.warning(f"[{self.port_name}] Error parsing sent_timestamp: {e}")
                    
                    items_to_keep.append(item)
                
                if items_removed > 0:
                    self.buffer.clear()
                    for item in items_to_keep:
                        self.buffer.append(item)
                    logger.info(f"[{self.port_name}] Cleaned up {items_removed} old sent messages from buffer")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error cleaning up old buffer: {e}")
    

    def flush_buffer(self):
        """Send all buffered data when connection is restored - SAFE VERSION"""
        if not self.tcp_connected or not self.tcp_socket:
            return

        # Step 1: Snapshot unsent items with indices
        with self.buffer_lock:
            if not self.buffer:
                return

            unsent_items = [
                (idx, item)
                for idx, item in enumerate(self.buffer)
                if item.get('sent') == 0
            ]

        if not unsent_items:
            self.cleanup_old_buffer()
            return

        logger.info(f"[{self.port_name}] Flushing {len(unsent_items)} buffered messages")

        # Step 2: Send data WITHOUT holding lock
        successfully_sent_indices = []

        for idx, item in unsent_items:
            try:
                self.tcp_socket.sendall(item['data'])
                successfully_sent_indices.append(idx)
                self.update_status(
                    'messages_sent',
                    self.status['messages_sent'] + 1
                )
            except Exception as e:
                logger.error(f"[{self.port_name}] Error flushing buffer at index {idx}: {e}")

                # Mark TCP as disconnected
                self.tcp_connected = False
                self.update_status('tcp_connected', False)

                try:
                    self.tcp_socket.close()
                except:
                    pass

                self.tcp_socket = None
                break  # STOP on first failure

        # Step 3: Mark sent items atomically
        if successfully_sent_indices:
            with self.buffer_lock:
                sent_timestamp = datetime.now().isoformat()

                for idx in successfully_sent_indices:
                    if idx < len(self.buffer):
                        self.buffer[idx]['sent'] = 1
                        self.buffer[idx]['sent_timestamp'] = sent_timestamp

            # Persist buffer AFTER marking sent
            self.save_buffer()

        # Step 4: Log + cleanup
        with self.buffer_lock:
            unsent_count = sum(
                1 for item in self.buffer if item.get('sent') == 0
            )

        logger.info(
            f"[{self.port_name}] Buffer flush complete. Remaining unsent: {unsent_count}"
        )

        self.cleanup_old_buffer()

   
    
    def send_data(self, data):
        """Send data via TCP or buffer it if connection is lost - FIXED VERSION"""
        if self.tcp_connected and self.tcp_socket:
            try:
                self.tcp_socket.sendall(data)
                self.update_status('messages_sent', self.status['messages_sent'] + 1)
                return True
            except Exception as e:
                logger.error(f"[{self.port_name}] Error sending data via TCP: {e}")
                self.tcp_connected = False
                self.update_status('tcp_connected', False)
                
                # Close the broken socket to force reconnection
                try:
                    self.tcp_socket.close()
                except:
                    pass
                self.tcp_socket = None
                
                # Add to buffer AFTER marking TCP as disconnected
                self.add_to_buffer(data)
                return False
        else:
            self.add_to_buffer(data)
            return False
    
    def serial_reader_thread(self):
        """Thread to read data from serial port and accumulate before sending"""
        logger.info(f"[{self.port_name}] Serial reader thread started")
        reconnect_interval = self.port_config.get('reconnect_interval', 5)
        send_delay = self.port_config.get('send_delay', 5)  # Wait 5 seconds after last data
        check_interval = 0.1  # Check every 100ms
        last_pending_save = time.time()
        pending_save_interval = 2  # Save pending data every 2 seconds
        
        while self.running:
            if not self.serial_connected:
                if not self.connect_serial():
                    if self.running:  # Only sleep if still running
                        time.sleep(reconnect_interval)
                    continue
            
            try:
                if not self.running:  # Check if we should stop
                    break
                
                # Read incoming serial data and accumulate it
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data and self.running:  # Check running flag before processing
                        with self.serial_accumulator_lock:
                            self.serial_accumulator.extend(data)
                            self.last_serial_data_time = time.time()
                        logger.debug(f"[{self.port_name}] Accumulated {len(data)} bytes (total: {len(self.serial_accumulator)} bytes)")
                        
                        # Periodically save pending data to database for persistence
                        if time.time() - last_pending_save >= pending_save_interval:
                            self.save_pending_data()
                            last_pending_save = time.time()
                else:
                    # Check if we should send accumulated data
                    with self.serial_accumulator_lock:
                        if (self.serial_accumulator and 
                            self.last_serial_data_time and 
                            (time.time() - self.last_serial_data_time) >= send_delay):
                            
                            # Send all accumulated data
                            data_to_send = bytes(self.serial_accumulator)
                            total_bytes = len(data_to_send)
                            logger.info(f"[{self.port_name}] Sending accumulated data: {total_bytes} bytes (idle for {send_delay}s)")
                            
                            if self.send_data(data_to_send):
                                logger.info(f"[{self.port_name}] Successfully sent {total_bytes} bytes")
                                
                                # Clear accumulator after successful send
                                self.serial_accumulator.clear()
                                self.last_serial_data_time = None
                                
                                # Clear pending data from database (only after successful send)
                                self.save_pending_data()
                            else:
                                logger.warning(f"[{self.port_name}] Failed to send {total_bytes} bytes - data buffered, will retry")
                                # Data is already in buffer table, accumulator stays in PENDING_ACCUMULATOR
                                # Clear accumulator since it's now in regular buffer
                                self.serial_accumulator.clear()
                                self.last_serial_data_time = None
                                # Clear PENDING_ACCUMULATOR since data moved to regular buffer
                                self.save_pending_data()
                    
                    time.sleep(check_interval)
                    
            except serial.SerialException as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"[{self.port_name}] Serial read error: {e}")
                    self.serial_connected = False
                    self.update_status('serial_connected', False)
                    self.update_status('last_error', f"Serial read error: {str(e)}")
                    time.sleep(reconnect_interval)
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"[{self.port_name}] Unexpected error in serial reader: {e}")
                    time.sleep(1)
        
        # Send any remaining data before stopping
        with self.serial_accumulator_lock:
            if self.serial_accumulator:
                data_to_send = bytes(self.serial_accumulator)
                logger.info(f"[{self.port_name}] Sending final accumulated data on shutdown: {len(data_to_send)} bytes")
                self.send_data(data_to_send)
                self.serial_accumulator.clear()
        
        # Save any remaining pending data to database
        self.save_pending_data()
        
        logger.info(f"[{self.port_name}] Serial reader thread stopped")
    
  
    def tcp_reconnect_thread(self):
        """Thread to maintain and verify TCP connection"""
        logger.info(f"[{self.port_name}] TCP reconnect thread started")
        reconnect_interval = self.port_config.get('reconnect_interval', 5)

        while self.running:
            if self.tcp_connected and self.tcp_socket:
                try:
                    self.tcp_socket.settimeout(0.5)
                    data = self.tcp_socket.recv(1, socket.MSG_PEEK)

                    if data == b'':
                        raise ConnectionError("TCP peer closed connection")

                except Exception:
                    logger.warning(f"[{self.port_name}] TCP connection lost")
                    self.tcp_connected = False
                    self.update_status('tcp_connected', False)

                    try:
                        self.tcp_socket.close()
                    except:
                        pass

                    self.tcp_socket = None

            if not self.tcp_connected and self.running:
                self.connect_tcp()
                time.sleep(reconnect_interval)
            else:
                time.sleep(1)

        logger.info(f"[{self.port_name}] TCP reconnect thread stopped")


    
    def cleanup_thread(self):
        """Thread to periodically clean up old sent messages from buffer"""
        logger.info(f"[{self.port_name}] Buffer cleanup thread started")
        cleanup_interval = 30  # Check every 30 seconds
        
        while self.running:
            try:
                # Clean up old sent data
                self.cleanup_old_buffer()
                # Save buffer after cleanup
                self.save_buffer()
                
                time.sleep(cleanup_interval)
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"[{self.port_name}] Error in cleanup thread: {e}")
                    time.sleep(cleanup_interval)
        
        logger.info(f"[{self.port_name}] Buffer cleanup thread stopped")
    
    def start(self):
        """Start the forwarder for this port"""
        if self.running:
            logger.warning(f"[{self.port_name}] Forwarder is already running")
            return False
        
        logger.info(f"[{self.port_name}] Starting forwarder")
        self.running = True
        
        # Start threads
        serial_thread = threading.Thread(target=self.serial_reader_thread, daemon=True)
        tcp_thread = threading.Thread(target=self.tcp_reconnect_thread, daemon=True)
        cleanup_thread = threading.Thread(target=self.cleanup_thread, daemon=True)
        
        self.threads = [serial_thread, tcp_thread, cleanup_thread]
        
        for thread in self.threads:
            thread.start()
        
        logger.info(f"[{self.port_name}] Forwarder started successfully")
        return True
    
    def stop(self):
        """Stop the forwarder for this port - FIXED VERSION"""
        if not self.running:
            logger.warning(f"[{self.port_name}] Forwarder is not running")
            return False
        
        logger.info(f"[{self.port_name}] Stopping forwarder")
        
        # CRITICAL FIX: Set running flag to False FIRST
        self.running = False
        
        # Wait for ALL threads to finish BEFORE saving buffer
        logger.debug(f"[{self.port_name}] Waiting for {len(self.threads)} threads to finish")
        for i, thread in enumerate(self.threads, 1):
            if thread.is_alive():
                logger.debug(f"[{self.port_name}] Waiting for thread {i}/{len(self.threads)}")
                thread.join(timeout=5)  # Increased timeout
                if thread.is_alive():
                    logger.warning(f"[{self.port_name}] Thread {i} did not stop within timeout")
        
        logger.info(f"[{self.port_name}] All threads stopped")
        
        # Save any pending accumulated data first
        try:
            with self.serial_accumulator_lock:
                pending_count = len(self.serial_accumulator)
            
            if pending_count > 0:
                logger.info(f"[{self.port_name}] Saving {pending_count} bytes of pending accumulated data before shutdown")
                self.save_pending_data()
        except Exception as e:
            logger.error(f"[{self.port_name}] Error saving pending data during stop: {e}")
        
        # NOW save buffer - threads are stopped, no more data will be added
        try:
            with self.buffer_lock:
                unsent_count = len([item for item in self.buffer if item.get('sent') == 0])
            
            if unsent_count > 0:
                logger.info(f"[{self.port_name}] Saving {unsent_count} unsent messages to database before shutdown")
            
            self.save_buffer()
            logger.info(f"[{self.port_name}] Buffer saved successfully")
        except Exception as e:
            logger.error(f"[{self.port_name}] CRITICAL: Error saving buffer during stop: {e}")
        
        # Close serial connection
        try:
            if self.serial_port:
                if hasattr(self.serial_port, 'is_open') and self.serial_port.is_open:
                    self.serial_port.close()
                    logger.debug(f"[{self.port_name}] Serial port closed")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error closing serial port: {e}")
        
        # Close TCP connection
        try:
            if self.tcp_socket:
                self.tcp_socket.close()
                logger.debug(f"[{self.port_name}] TCP socket closed")
        except Exception as e:
            logger.error(f"[{self.port_name}] Error closing TCP socket: {e}")
        
        self.serial_connected = False
        self.tcp_connected = False
        self.update_status('serial_connected', False)
        self.update_status('tcp_connected', False)
        
        logger.info(f"[{self.port_name}] Forwarder stopped successfully")
        return True


class MultiPortForwarder:
    """Manages multiple serial port to TCP forwarders"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.forwarders = {}
        self.status_lock = threading.Lock()
        
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
        """Return default configuration with a single port"""
        return {
            'ports': [
                {
                    'name': 'port1',
                    'serial_port': '/dev/ttyUSB0',
                    'serial_baudrate': 9600,
                    'serial_bytesize': 8,
                    'serial_parity': 'N',
                    'serial_stopbits': 1,
                    'serial_timeout': 1,
                    'serial_xonxoff': True,
                    'serial_rtscts': False,
                    'tcp_host': 'localhost',
                    'tcp_port': 5000,
                    'buffer_size': 10000,
                    'reconnect_interval': 5,
                    'send_delay': 5
                }
            ]
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
    
    def start(self):
        """Start all port forwarders"""
        ports = self.config.get('ports', [])
        
        if not ports:
            logger.error("No ports configured")
            return False
        
        logger.info(f"Starting {len(ports)} port forwarders")
        
        for port_config in ports:
            port_name = port_config.get('name', port_config.get('serial_port', 'unknown'))
            
            try:
                forwarder = SinglePortForwarder(port_name, port_config)
                if forwarder.start():
                    self.forwarders[port_name] = forwarder
                else:
                    logger.error(f"Failed to start forwarder for {port_name}")
            except Exception as e:
                logger.error(f"Error creating forwarder for {port_name}: {e}")
        
        logger.info(f"Successfully started {len(self.forwarders)} forwarders")
        return len(self.forwarders) > 0
    
    def stop(self):
        """Stop all port forwarders"""
        logger.info(f"Stopping {len(self.forwarders)} forwarders")
        
        for port_name, forwarder in self.forwarders.items():
            try:
                forwarder.stop()
            except Exception as e:
                logger.error(f"Error stopping forwarder for {port_name}: {e}")
        
        self.forwarders.clear()
        logger.info("All forwarders stopped")
        return True
    
    def get_status(self):
        """Get status of all forwarders"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'forwarders': {}
        }
        
        for port_name, forwarder in self.forwarders.items():
            status['forwarders'][port_name] = forwarder.get_status()
        
        return status
    
    def get_forwarder(self, port_name):
        """Get a specific forwarder by port name"""
        return self.forwarders.get(port_name)


# Backward compatibility: Alias for SinglePortForwarder
class SerialToTCPForwarder(SinglePortForwarder):
    """Backward compatible class - use SinglePortForwarder instead"""
    def __init__(self, config_file='config.json', buffer_file='buffer.pkl'):
        # Load config for backward compatibility
        config = self.load_config_from_file(config_file)
        super().__init__('default', config, 'buffers')
        self.config_file_compat = config_file
        self.buffer_file_compat = buffer_file
    
    @staticmethod
    def load_config_from_file(config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                # Handle both old single-port and new multi-port formats
                if 'ports' in data:
                    return data['ports'][0] if data['ports'] else {}
                else:
                    return data
        except:
            return {}


if __name__ == '__main__':
    forwarder = MultiPortForwarder()
    forwarder.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt - shutting down gracefully")
        forwarder.stop()
        logger.info("Shutdown complete")