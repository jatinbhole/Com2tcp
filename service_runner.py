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
if sys.version_info < (3, 8) or sys.version_info >= (3, 9):
    print("Error: Python 3.8 only is required")
    print(f"Current version: {sys.version}")
    sys.exit(1)

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
            logger.info("Starting Web Service on 0.0.0.0:8080")
            # Disable Flask's default signal handlers to use our own
            app.run(
                host='0.0.0.0',
                port=8081,
                debug=False,
                use_reloader=False,
                use_debugger=False,
                threaded=True
            )
        except Exception as e:
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
            
            # Start Web Service (blocking)
            self.run_web_service()
        
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
            
            # Stop Serial Forwarder
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
                self.forwarder_thread.join(timeout=5)
                if self.forwarder_thread.is_alive():
                    logger.warning("Forwarder thread did not stop within timeout")
            
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
