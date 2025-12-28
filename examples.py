#!/usr/bin/env python3
"""
Example: Using the Serial Forwarder Programmatically

This example shows how to use the SerialToTCPForwarder class
in your own Python scripts.
"""

from serial_forwarder import SerialToTCPForwarder
import time

def example_1_basic_usage():
    """Example 1: Basic usage with default configuration"""
    print("=== Example 1: Basic Usage ===")
    
    # Create forwarder with default config from config.json
    forwarder = SerialToTCPForwarder()
    
    # Start forwarding
    forwarder.start()
    
    # Run for 30 seconds
    print("Forwarding for 30 seconds...")
    time.sleep(30)
    
    # Stop
    forwarder.stop()
    print("Done!\n")


def example_2_custom_config():
    """Example 2: Using custom configuration"""
    print("=== Example 2: Custom Configuration ===")
    
    # Create forwarder
    forwarder = SerialToTCPForwarder()
    
    # Set custom configuration
    custom_config = {
        'serial_port': '/dev/ttyUSB0',
        'serial_baudrate': 115200,
        'serial_bytesize': 8,
        'serial_parity': 'N',
        'serial_stopbits': 1,
        'serial_timeout': 1,
        'tcp_host': '192.168.1.100',
        'tcp_port': 8000,
        'buffer_size': 5000,
        'reconnect_interval': 3
    }
    
    forwarder.save_config(custom_config)
    forwarder.start()
    
    print("Running with custom config...")
    time.sleep(30)
    
    forwarder.stop()
    print("Done!\n")


def example_3_monitoring():
    """Example 3: Monitoring status while running"""
    print("=== Example 3: Status Monitoring ===")
    
    forwarder = SerialToTCPForwarder()
    forwarder.start()
    
    # Monitor for 60 seconds
    for i in range(12):  # 12 iterations * 5 seconds = 60 seconds
        time.sleep(5)
        
        status = forwarder.get_status()
        
        print(f"\n--- Status Update {i+1} ---")
        print(f"Running: {forwarder.running}")
        print(f"Serial Connected: {status['serial_connected']}")
        print(f"TCP Connected: {status['tcp_connected']}")
        print(f"Messages Sent: {status['messages_sent']}")
        print(f"Messages Buffered: {status['messages_buffered']}")
        print(f"Buffer Size: {status['buffer_size']}")
        
        if status['last_error']:
            print(f"Last Error: {status['last_error']}")
    
    forwarder.stop()
    print("\nDone!\n")


def example_4_error_handling():
    """Example 4: Handling errors gracefully"""
    print("=== Example 4: Error Handling ===")
    
    try:
        forwarder = SerialToTCPForwarder()
        
        # Try to start
        if forwarder.start():
            print("✓ Forwarder started successfully")
            
            # Run for a while
            for i in range(10):
                time.sleep(5)
                status = forwarder.get_status()
                
                # Check for errors
                if status['last_error']:
                    print(f"⚠ Warning: {status['last_error']}")
                
                # Check connections
                if not status['serial_connected']:
                    print("⚠ Serial port disconnected, will retry...")
                
                if not status['tcp_connected']:
                    print(f"⚠ TCP disconnected, buffer size: {status['buffer_size']}")
            
            forwarder.stop()
            print("✓ Forwarder stopped cleanly")
        else:
            print("✗ Failed to start forwarder")
            
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        if forwarder:
            forwarder.stop()
    except Exception as e:
        print(f"✗ Error: {e}")
        if forwarder:
            forwarder.stop()
    
    print("Done!\n")


def example_5_long_running():
    """Example 5: Long-running service with graceful shutdown"""
    print("=== Example 5: Long-Running Service ===")
    print("Press Ctrl+C to stop\n")
    
    forwarder = SerialToTCPForwarder()
    
    try:
        forwarder.start()
        
        print("Service started. Monitoring every 30 seconds...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            time.sleep(30)
            
            status = forwarder.get_status()
            
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]")
            print(f"  Serial: {'✓' if status['serial_connected'] else '✗'}")
            print(f"  TCP: {'✓' if status['tcp_connected'] else '✗'}")
            print(f"  Sent: {status['messages_sent']}, Buffered: {status['buffer_size']}")
            
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        forwarder.stop()
        print("✓ Service stopped")


if __name__ == '__main__':
    import sys
    
    print("\nSerial to TCP Forwarder - Usage Examples")
    print("=" * 60)
    print("\nAvailable examples:")
    print("  1 - Basic usage with default config")
    print("  2 - Custom configuration")
    print("  3 - Status monitoring")
    print("  4 - Error handling")
    print("  5 - Long-running service (Ctrl+C to stop)")
    print()
    
    choice = input("Select example (1-5) or press Enter for example 3: ").strip()
    
    if not choice:
        choice = '3'
    
    examples = {
        '1': example_1_basic_usage,
        '2': example_2_custom_config,
        '3': example_3_monitoring,
        '4': example_4_error_handling,
        '5': example_5_long_running
    }
    
    example_func = examples.get(choice)
    
    if example_func:
        print()
        example_func()
    else:
        print("Invalid choice!")
