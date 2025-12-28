#!/usr/bin/env python3
"""
Simple TCP Test Server
Receives data from the serial forwarder for testing purposes
"""
import socket
import sys
from datetime import datetime

def start_test_server(host='0.0.0.0', port=5000):
    """Start a simple TCP server to receive forwarded serial data"""
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(1)
        
        print(f"TCP Test Server started on {host}:{port}")
        print("Waiting for connection from serial forwarder...")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"\n[{datetime.now()}] Connection from {client_address}")
            
            try:
                while True:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] Received {len(data)} bytes:")
                    
                    # Try to decode as text, otherwise show hex
                    try:
                        decoded = data.decode('utf-8', errors='replace')
                        print(f"  Text: {decoded}")
                    except:
                        pass
                    
                    print(f"  Hex: {data.hex()}")
                    print("-" * 60)
                    
            except Exception as e:
                print(f"Error handling client: {e}")
            finally:
                print(f"[{datetime.now()}] Connection closed")
                client_socket.close()
                
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()
        print("Server stopped")


if __name__ == '__main__':
    # Parse command line arguments
    host = '0.0.0.0'
    port = 5000
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    if len(sys.argv) > 2:
        host = sys.argv[2]
    
    start_test_server(host, port)
