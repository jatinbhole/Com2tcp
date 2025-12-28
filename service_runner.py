#!/usr/bin/env python3
"""
Unified Service Runner
Runs both the Web Service (Flask) and Serial Forwarder as a single service
"""
import sys
import threading
import logging
import signal
import time

# Check Python version
if sys.version_info < (3, 8):
    print("Error: Python 3.8 or higher is required")
    print(f"Current version: {sys.version}")
    sys.exit(1)

from serial_forwarder import MultiPortForwarder
from web_service import app

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
        self.flask_thread = None
        self.shutdown_event = threading.Event()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.shutdown()
    
    def run_web_service(self):
        """Run Flask web service in a thread"""
        try:
            logger.info("Starting Web Service on 0.0.0.0:8080")
            app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
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
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in forwarder: {e}")
        finally:
            logger.info("Serial Forwarder stopped")
    
    def start(self):
        """Start both services"""
        logger.info("=" * 60)
        logger.info("Starting Unified Serial Forwarder Service")
        logger.info("=" * 60)
        
        # Start Serial Forwarder in a thread
        forwarder_thread = threading.Thread(
            target=self.run_forwarder,
            daemon=False,
            name="ForwarderThread"
        )
        forwarder_thread.start()
        
        # Give forwarder time to initialize
        time.sleep(2)
        
        # Start Web Service (blocking)
        try:
            self.run_web_service()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()
            # Wait for forwarder thread to finish
            forwarder_thread.join(timeout=5)
    
    def shutdown(self):
        """Gracefully shutdown both services"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Shutting down all services...")
        
        try:
            self.forwarder.stop()
            logger.info("Serial Forwarder stopped")
        except Exception as e:
            logger.error(f"Error stopping forwarder: {e}")
        
        logger.info("=" * 60)
        logger.info("All services stopped")
        logger.info("=" * 60)


if __name__ == '__main__':
    runner = ServiceRunner()
    runner.start()
