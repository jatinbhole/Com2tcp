#!/usr/bin/env python3
"""
Unified Service Runner
Runs both the Web Service (Flask) and Serial Forwarder as a single service
Supports graceful shutdown with proper cleanup
Modified with forwarder
Requirements:
- Python 3.8 only
"""
import sys
import threading
import logging
import signal
import time
import atexit
import os

# Check Python version - 3.8 only
#if sys.version_info < (3, 8) or sys.version_info >= (3, 9):
#    print("Error: Python 3.8 only is required")
#    print(f"Current version: {sys.version}")
#    sys.exit(1)

from serial_forwarder import MultiPortForwarder
#from web_service import app
from web_service import app, set_forwarder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ServiceRunner:
    """Manages both Web Service and Serial Forwarder"""
    
    def __init__(self):
        self.running = True
        self.forwarder = MultiPortForwarder()
        set_forwarder(self.forwarder)
        self.flask_thread = None
        self.forwarder_thread = None
        self.server = None  # Werkzeug server instance
        self.shutdown_event = threading.Event()
        self.shutdown_lock = threading.Lock()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}. Starting graceful shutdown...")
        self.shutdown()
        sys.exit(0)
    
    def run_web_service(self):
        """Run Flask web service in a thread"""
        try:
            logger.info("Starting Web Service on 0.0.0.0:8081")
            # Disable Flask's default signal handlers to use our own
            from werkzeug.serving import make_server
            self.server = make_server('0.0.0.0', 9001, app, threaded=True)
            self.server.serve_forever()
        except Exception as e:
            if self.running:  # Only log if not shutting down
                logger.error(f"Error in web service: {e}")
        finally:
            logger.info("Web Service stopped")
    
    def run_forwarder(self):
        """Run serial forwarder in a thread"""
        try:
            logger.info("Starting Serial Forwarder")
            self.forwarder.start()
            
            # Keep the forwarder running
            while self.running:
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in forwarder: {e}")
        finally:
            logger.info("Serial Forwarder thread exiting")
    
    def start(self):
        """Start both services"""
        logger.info("=" * 70)
        logger.info("Starting Unified Serial Forwarder Service")
        logger.info("=" * 70)
        
        try:
            # Start Serial Forwarder in a thread
            self.forwarder_thread = threading.Thread(
                target=self.run_forwarder,
                daemon=False,
                name="ForwarderThread"
            )
            self.forwarder_thread.start()
            
            # Give forwarder time to initialize
            time.sleep(2)
            
            # Start Web Service in a thread
            self.flask_thread = threading.Thread(
                target=self.run_web_service,
                daemon=False,
                name="FlaskThread"
            )
            self.flask_thread.start()
            
            # Wait for both threads
            while self.running:
                time.sleep(0.5)
        
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error during service startup: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown both services"""
        with self.shutdown_lock:
            if not self.running:
                return
            
            self.running = False
            self.shutdown_event.set()
            
            logger.info("=" * 70)
            logger.info("Starting graceful shutdown sequence...")
            logger.info("=" * 70)
            
            # Stop Serial Forwarder first (most important)
            try:
                logger.info("Stopping Serial Forwarder...")
                if self.forwarder:
                    self.forwarder.stop()
                logger.info("Serial Forwarder stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping forwarder: {e}")
            
            # Wait for forwarder thread to finish
            if self.forwarder_thread and self.forwarder_thread.is_alive():
                logger.info("Waiting for Forwarder thread to finish...")
                self.forwarder_thread.join(timeout=3)
                if self.forwarder_thread.is_alive():
                    logger.warning("Forwarder thread did not stop within timeout")
            
            # Stop Web Service
            try:
                logger.info("Stopping Web Service...")
                if self.server:
                    # Shutdown in a separate thread to avoid blocking
                    shutdown_thread = threading.Thread(target=self.server.shutdown, daemon=True)
                    shutdown_thread.start()
                    shutdown_thread.join(timeout=2)
                logger.info("Web Service stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping web service: {e}")
            
            # Wait for flask thread to finish
            if self.flask_thread and self.flask_thread.is_alive():
                logger.info("Waiting for Flask thread to finish...")
                self.flask_thread.join(timeout=2)
                if self.flask_thread.is_alive():
                    logger.warning("Flask thread did not stop within timeout")
            
            logger.info("=" * 70)
            logger.info("All services stopped gracefully")
            logger.info("=" * 70)
    
    def cleanup(self):
        """Cleanup on exit"""
        if self.running:
            logger.info("Performing cleanup...")
            self.shutdown()


if __name__ == '__main__':
    runner = ServiceRunner()
    runner.start()
