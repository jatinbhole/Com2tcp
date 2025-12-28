#!/usr/bin/env python3
"""
Authentication System Test Script
Tests login, password change, and logout functionality
"""

import sys
import time
import subprocess
import requests
from requests.sessions import Session

def test_authentication():
    """Test authentication system"""
    
    print("=" * 70)
    print("Serial to TCP Forwarder - Authentication System Tests")
    print("=" * 70)
    print()
    
    # Create session for cookies
    session = Session()
    base_url = "http://localhost:8080"
    
    # Test 1: Access login page
    print("Test 1: Accessing login page...")
    try:
        response = session.get(f"{base_url}/login", timeout=5)
        if response.status_code == 200 and "Login" in response.text:
            print("✓ Login page accessible")
        else:
            print(f"✗ Login page failed (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to service: {e}")
        return False
    
    print()
    
    # Test 2: Failed login with wrong credentials
    print("Test 2: Testing failed login with wrong credentials...")
    response = session.post(
        f"{base_url}/login",
        data={"username": "admin", "password": "wrongpassword"},
        timeout=5
    )
    if response.status_code == 200 and "Invalid" in response.text:
        print("✓ Failed login rejected correctly")
    else:
        print(f"✗ Failed login not handled correctly (status: {response.status_code})")
    
    print()
    
    # Test 3: Successful login with default credentials
    print("Test 3: Testing successful login with default credentials...")
    response = session.post(
        f"{base_url}/login",
        data={"username": "admin", "password": "admin123"},
        timeout=5
    )
    if response.status_code == 200 and ("Ports" in response.text or "Configuration" in response.text):
        print("✓ Login successful - authenticated user can access dashboard")
    else:
        print(f"✗ Login failed or dashboard not accessible (status: {response.status_code})")
        return False
    
    print()
    
    # Test 4: Accessing protected route without login
    print("Test 4: Testing access to protected routes...")
    new_session = Session()  # New session without login cookie
    response = new_session.get(f"{base_url}/", timeout=5, allow_redirects=False)
    if response.status_code == 302 and "login" in response.headers.get("Location", ""):
        print("✓ Protected routes properly redirect to login")
    else:
        print(f"✗ Protected route redirect failed (status: {response.status_code})")
    
    print()
    
    # Test 5: Password change endpoint
    print("Test 5: Testing password change endpoint...")
    response = session.post(
        f"{base_url}/api/change_password",
        json={
            "old_password": "admin123",
            "new_password": "newpass123",
            "confirm_password": "newpass123"
        },
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✓ Password change successful")
            
            # Test 5b: Login with new password
            print()
            print("Test 5b: Testing login with new password...")
            new_session = Session()
            response = new_session.post(
                f"{base_url}/login",
                data={"username": "admin", "password": "newpass123"},
                timeout=5
            )
            if response.status_code == 200 and ("Ports" in response.text or "Configuration" in response.text):
                print("✓ Login with new password successful")
                
                # Restore original password
                response = new_session.post(
                    f"{base_url}/api/change_password",
                    json={
                        "old_password": "newpass123",
                        "new_password": "admin123",
                        "confirm_password": "admin123"
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    print("✓ Password restored to original")
            else:
                print(f"✗ Login with new password failed")
        else:
            print(f"✗ Password change failed: {data.get('error')}")
    else:
        print(f"✗ Password change endpoint failed (status: {response.status_code})")
    
    print()
    
    # Test 6: Logout
    print("Test 6: Testing logout...")
    response = session.get(f"{base_url}/logout", timeout=5)
    if response.status_code == 200 or (response.status_code == 302 and "login" in response.headers.get("Location", "")):
        print("✓ Logout successful")
        
        # Verify session is cleared
        response = session.get(f"{base_url}/", timeout=5, allow_redirects=False)
        if response.status_code == 302:
            print("✓ Session properly cleared - redirect to login")
        else:
            print(f"✗ Session not cleared (status: {response.status_code})")
    else:
        print(f"✗ Logout failed (status: {response.status_code})")
    
    print()
    print("=" * 70)
    print("All tests completed!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    # Give the service time to start if just launched
    time.sleep(2)
    
    try:
        test_authentication()
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)
