"""
Test script for HTTP-based serial forwarder system
"""
import requests
import time

# Server URL
SERVER_URL = "http://localhost:5000"

def test_server_status():
    """Test if server is running"""
    print("Testing server status...")
    try:
        response = requests.get(f"{SERVER_URL}/status", timeout=5)
        if response.status_code == 200:
            print(f"✓ Server is running: {response.json()}")
            return True
        else:
            print(f"✗ Server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Server not reachable: {e}")
        return False


def test_forward_data():
    """Test forwarding data to TCP port"""
    print("\nTesting data forwarding...")
    
    # Test data (hex-encoded "Hello World!")
    test_data = "48656c6c6f20576f726c6421"
    
    payload = {
        "data": test_data,
        "tcp_port": 8090,
        "tcp_host": "localhost",
        "source_port": "test_script"
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/forward",
            json=payload,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✓ Data forwarded successfully")
            return True
        else:
            print("✗ Data forwarding failed")
            return False
            
    except Exception as e:
        print(f"✗ Error forwarding data: {e}")
        return False


def test_invalid_request():
    """Test invalid request handling"""
    print("\nTesting invalid request handling...")
    
    # Missing required field
    payload = {
        "data": "48656c6c6f"
        # Missing tcp_port
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/forward",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 400:
            print(f"✓ Server correctly rejected invalid request: {response.json()}")
            return True
        else:
            print(f"✗ Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_server_info():
    """Test server info endpoint"""
    print("\nTesting server info endpoint...")
    try:
        response = requests.get(f"{SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            info = response.json()
            print(f"✓ Server info retrieved")
            print(f"  Service: {info.get('service')}")
            print(f"  Version: {info.get('version')}")
            print(f"  Endpoints: {list(info.get('endpoints', {}).keys())}")
            return True
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("HTTP Serial Forwarder System - Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: Server status
    results.append(("Server Status", test_server_status()))
    
    if results[0][1]:  # Only continue if server is running
        # Test 2: Server info
        results.append(("Server Info", test_server_info()))
        
        # Test 3: Forward data
        results.append(("Forward Data", test_forward_data()))
        
        # Test 4: Invalid request
        results.append(("Invalid Request", test_invalid_request()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:20} {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\nPassed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")


if __name__ == '__main__':
    main()
