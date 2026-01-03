# Quick Start Guide - HTTP-Based Serial Forwarder

## System Overview

This system implements a two-part serial-to-TCP forwarder with buffering:

1. **Client** ([serial_forwarder_http.py](serial_forwarder_http.py)): Reads serial data, buffers for 5 seconds, then sends via HTTP POST
2. **Server** ([tcp_forwarder_server.py](tcp_forwarder_server.py)): Receives HTTP POST and forwards to TCP socket

## Quick Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Client

Edit [config_http.json](config_http.json):

```json
{
    "ports": [
        {
            "name": "port1",
            "serial_port": "COM3",           // Your serial port
            "serial_baudrate": 9600,
            "serial_bytesize": 8,
            "serial_parity": "N",
            "serial_stopbits": 1,
            "serial_timeout": 1,
            "serial_xonxoff": true,
            "serial_rtscts": false,
            "http_url": "http://localhost:5000/forward",  // Server URL
            "tcp_host": "192.168.21.18",     // Target TCP host
            "tcp_port": 8090,                 // Target TCP port
            "reconnect_interval": 5
        }
    ]
}
```

### Step 3: Start the Server

```bash
# Terminal 1
python tcp_forwarder_server.py
```

Server will start on `http://0.0.0.0:5000`

### Step 4: Start the Client

```bash
# Terminal 2
python serial_forwarder_http.py
```

## How It Works

### Data Flow

```
Serial Device → Client reads data → Buffer (5 sec) → HTTP POST → Server → TCP Socket → Target Device
```

### Buffering Logic

1. Client receives data from serial port
2. Data is added to buffer
3. Timer starts/resets with each byte received
4. After **5 seconds** of no new data, all buffered data is sent via HTTP POST
5. Buffer is cleared and ready for next batch

### Example Scenario

```
Time  | Event
------|-------------------------------------------------------
0.0s  | Serial data arrives: "Hello"
0.1s  | Serial data arrives: " World"
5.1s  | No more data for 5 seconds → Send "Hello World" via HTTP POST
5.2s  | Server receives POST, forwards to TCP 192.168.21.18:8090
```

## Testing the System

### Test 1: Server Health Check

```bash
curl http://localhost:5000/status
```

Expected response:
```json
{
    "status": "running",
    "service": "TCP Forwarder Server",
    "version": "1.0"
}
```

### Test 2: Manual POST Test

```bash
# Send hex-encoded "Hello" to TCP port 8090
curl -X POST http://localhost:5000/forward \
  -H "Content-Type: application/json" \
  -d '{"data":"48656c6c6f", "tcp_host":"192.168.21.18", "tcp_port":8090}'
```

Expected response:
```json
{
    "success": true,
    "message": "Successfully sent 5 bytes to 192.168.21.18:8090",
    "bytes_sent": 5,
    "target": "192.168.21.18:8090"
}
```

### Test 3: Run Automated Tests

```bash
python test_http_system.py
```

## Monitoring

### Client Logs

Watch for these messages:
- `Connected to serial port COM3` - Serial connection OK
- `Added X bytes to buffer` - Data being buffered
- `Buffer timeout reached, sending data` - 5 seconds passed, sending
- `Successfully sent data` - HTTP POST succeeded

### Server Logs

Watch for these messages:
- `Received request from port1: X bytes to 192.168.21.18:8090` - POST received
- `Connecting to 192.168.21.18:8090` - Opening TCP connection
- `Sent X bytes to 192.168.21.18:8090` - Data forwarded successfully

## Troubleshooting

### Client won't start
- Check serial port name (COM3 on Windows, /dev/ttyUSB0 on Linux)
- Verify port is not in use by another application
- Check serial port permissions (Linux: `sudo usermod -a -G dialout $USER`)

### HTTP POST fails
- Verify server is running: `curl http://localhost:5000/status`
- Check `http_url` in config matches server address
- Check firewall settings

### TCP forwarding fails
- Verify target TCP port is open and listening
- Check network connectivity to tcp_host
- Verify tcp_host and tcp_port in config are correct
- Check server logs for detailed error messages

### No data being sent
- Check if serial device is sending data
- Verify 5 seconds have passed since last byte
- Check client logs for buffer activity
- Reduce buffer timeout for testing (modify `buffer_timeout` in code)

## Advanced Configuration

### Remote Server

To use a remote server instead of localhost:

1. Start server on remote machine:
   ```bash
   python tcp_forwarder_server.py --host 0.0.0.0 --port 5000
   ```

2. Update client config:
   ```json
   "http_url": "http://192.168.1.100:5000/forward"
   ```

### Multiple Serial Ports

Add multiple ports to config:

```json
{
    "ports": [
        {
            "name": "port1",
            "serial_port": "COM3",
            ...
        },
        {
            "name": "port2",
            "serial_port": "COM4",
            ...
        }
    ]
}
```

### Custom Buffer Timeout

Edit [serial_forwarder_http.py](serial_forwarder_http.py), line ~30:

```python
self.buffer_timeout = 5.0  # Change to desired seconds
```

## Server API Reference

### POST /forward

Forward data to TCP port.

**Request:**
```json
{
    "data": "hex_string",      // Required: Hex-encoded data
    "tcp_port": 8090,          // Required: Target port
    "tcp_host": "localhost",   // Optional: Target host
    "source_port": "port1"     // Optional: Source identifier
}
```

**Success Response (200):**
```json
{
    "success": true,
    "message": "Successfully sent X bytes to host:port",
    "bytes_sent": X,
    "target": "host:port"
}
```

**Error Response (400/500):**
```json
{
    "success": false,
    "error": "Error description",
    "target": "host:port"
}
```

### GET /status

Health check.

**Response (200):**
```json
{
    "status": "running",
    "service": "TCP Forwarder Server",
    "version": "1.0"
}
```

### GET /

API documentation.

## Command Reference

### Start Server
```bash
# Default (0.0.0.0:5000)
python tcp_forwarder_server.py

# Custom port
python tcp_forwarder_server.py --port 8080

# Custom host and port
python tcp_forwarder_server.py --host 127.0.0.1 --port 8080

# Debug mode
python tcp_forwarder_server.py --debug
```

### Start Client
```bash
# Default config (config_http.json)
python serial_forwarder_http.py

# Custom config file
python serial_forwarder_http.py my_config.json
```

## Integration Examples

### With Python

```python
import requests

data = b"Hello World"
response = requests.post(
    'http://localhost:5000/forward',
    json={
        'data': data.hex(),
        'tcp_host': '192.168.21.18',
        'tcp_port': 8090
    }
)
print(response.json())
```

### With curl

```bash
# Send text "Test"
curl -X POST http://localhost:5000/forward \
  -H "Content-Type: application/json" \
  -d '{"data":"54657374", "tcp_host":"localhost", "tcp_port":8090}'
```

### With PowerShell

```powershell
$body = @{
    data = "48656c6c6f"  # "Hello" in hex
    tcp_host = "localhost"
    tcp_port = 8090
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/forward" `
    -Method Post `
    -Body $body `
    -ContentType "application/json"
```

## Production Deployment

### Linux Service (systemd)

Create `/etc/systemd/system/tcp-forwarder-server.service`:

```ini
[Unit]
Description=TCP Forwarder Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Com2tcp
ExecStart=/usr/bin/python3 tcp_forwarder_server.py --host 0.0.0.0 --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable tcp-forwarder-server
sudo systemctl start tcp-forwarder-server
```

### Windows Service

Use NSSM (Non-Sucking Service Manager):

```bash
nssm install TCPForwarderServer "C:\Python38\python.exe" "C:\path\to\tcp_forwarder_server.py"
nssm start TCPForwarderServer
```

## Security Considerations

1. **Authentication**: Server has no authentication - add if exposing to internet
2. **HTTPS**: Use HTTPS for production deployments
3. **Firewall**: Restrict server access to trusted IPs only
4. **Input Validation**: Server validates hex data format
5. **Rate Limiting**: Consider adding rate limiting for production

## Need Help?

- Check logs for detailed error messages
- Run test suite: `python test_http_system.py`
- Verify configuration matches your setup
- Ensure all dependencies are installed
- Check [README_HTTP.md](README_HTTP.md) for detailed documentation
