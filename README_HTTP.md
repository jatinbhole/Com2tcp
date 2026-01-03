# HTTP-Based Serial Forwarder with 5-Second Buffering

## Overview

This implementation provides a two-part system for forwarding serial data to TCP connections via HTTP POST:

### Client Side (serial_forwarder_http.py)
- Reads data from serial port(s)
- Buffers incoming serial data
- After 5 seconds of no new data, sends all buffered data via HTTP POST
- Sends data as hex-encoded string along with target TCP port

### Server Side (tcp_forwarder_server.py)
- Receives HTTP POST requests with data and TCP port
- Opens TCP socket to specified port
- Forwards the data to the TCP connection
- Returns success/failure response

## Architecture

```
Serial Device → Client (serial_forwarder_http.py) → HTTP POST → Server (tcp_forwarder_server.py) → TCP Socket → Target Device
```

## Files

- `serial_forwarder_http.py` - Client that reads serial and POSTs to server
- `tcp_forwarder_server.py` - Server that receives POST and forwards to TCP
- `config_http.json` - Configuration for client

## Configuration

### config_http.json

```json
{
    "ports": [
        {
            "name": "port1",
            "serial_port": "COM3",
            "serial_baudrate": 9600,
            "serial_bytesize": 8,
            "serial_parity": "N",
            "serial_stopbits": 1,
            "serial_timeout": 1,
            "serial_xonxoff": true,
            "serial_rtscts": false,
            "http_url": "http://localhost:5000/forward",
            "tcp_port": 8090,
            "reconnect_interval": 5
        }
    ]
}
```

### Parameters

- `http_url`: URL of the server endpoint (default: http://localhost:5000/forward)
- `tcp_port`: Target TCP port number to forward data to
- Buffer timeout is fixed at 5 seconds

## Usage

### Starting the Server

```bash
# Basic usage (listens on 0.0.0.0:5000)
python tcp_forwarder_server.py

# Custom host and port
python tcp_forwarder_server.py --host 0.0.0.0 --port 5000

# With debug mode
python tcp_forwarder_server.py --debug
```

### Starting the Client

```bash
# Uses config_http.json by default
python serial_forwarder_http.py
```

You need to modify the script to use `config_http.json` instead of `config.json`, or rename your config file.

## API Endpoint

### POST /forward

Receives data and forwards to TCP port.

**Request:**
```json
{
    "data": "48656c6c6f",  // Hex-encoded data
    "tcp_port": 8090,       // Required: Target TCP port
    "tcp_host": "192.168.21.18",  // Optional: Target host (default: localhost)
    "source_port": "port1"  // Optional: Source identifier
}
```

**Response (Success):**
```json
{
    "success": true,
    "message": "Successfully sent 5 bytes to 192.168.21.18:8090",
    "bytes_sent": 5,
    "target": "192.168.21.18:8090"
}
```

**Response (Error):**
```json
{
    "success": false,
    "error": "Connection refused by 192.168.21.18:8090",
    "target": "192.168.21.18:8090"
}
```

### GET /status

Health check endpoint.

**Response:**
```json
{
    "status": "running",
    "service": "TCP Forwarder Server",
    "version": "1.0"
}
```

### GET /

Information endpoint with API documentation.

## How It Works

### Client (serial_forwarder_http.py)

1. **Serial Reading Thread**
   - Continuously reads from serial port
   - Adds data to buffer
   - Updates timestamp of last data received

2. **Buffer Timeout Thread**
   - Checks every 500ms if buffer has data
   - If 5 seconds have passed since last data, sends buffered data via HTTP POST
   - Converts data to hex string for JSON transmission

3. **HTTP POST**
   - Sends JSON with data (hex), tcp_port, and source_port
   - Waits for server response
   - Logs success/failure

### Server (tcp_forwarder_server.py)

1. **Receives POST Request**
   - Validates JSON payload
   - Extracts data (hex), tcp_port, tcp_host

2. **Converts Hex to Bytes**
   - Decodes hex string back to binary data

3. **Forwards to TCP**
   - Opens socket to specified host:port
   - Sends data
   - Closes connection
   - Returns success/failure response

## Benefits

- **Decoupling**: Serial client and TCP target don't need direct connection
- **Buffering**: Aggregates data over 5 seconds for efficient transmission
- **Network Flexibility**: Can forward over HTTP to remote servers
- **Error Handling**: Server provides detailed error responses
- **Scalability**: Server can handle multiple clients simultaneously

## Error Handling

### Client Errors
- Serial port disconnection → Auto-reconnect
- HTTP POST failure → Logged, data lost (no persistent buffering in this version)

### Server Errors
- Invalid JSON → 400 Bad Request
- Missing fields → 400 Bad Request
- TCP connection failed → 500 Internal Server Error with details

## Requirements

```
pyserial>=3.5
Flask>=2.0.0
requests>=2.26.0
```

## Testing

### Test Server
```bash
# Terminal 1: Start server
python tcp_forwarder_server.py

# Terminal 2: Test with curl
curl -X POST http://localhost:5000/forward \
  -H "Content-Type: application/json" \
  -d '{"data":"48656c6c6f", "tcp_port":8090, "tcp_host":"localhost"}'
```

### Test Client
1. Configure `config_http.json` with your serial port
2. Start server: `python tcp_forwarder_server.py`
3. Start client: `python serial_forwarder_http.py`
4. Send data to serial port
5. Wait 5 seconds after last byte
6. Check server logs for forwarding activity

## Notes

- **5-Second Timeout**: Fixed at 5 seconds after last byte received
- **No Persistence**: Buffered data is lost if client crashes (can be added if needed)
- **Single Send**: Each 5-second timeout triggers one HTTP POST
- **Hex Encoding**: Data is sent as hex string for safe JSON transmission
- **Thread-Safe**: Uses locks for buffer access

## Future Enhancements

- Add persistent buffer (SQLite) to client
- Configurable buffer timeout
- Retry logic for failed HTTP POSTs
- Authentication for server endpoint
- WebSocket for bidirectional communication
- Batch multiple buffers in one POST
