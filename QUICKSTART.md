# Quick Start Guide

## Setup in 3 Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Setup

Edit `config.json` with your serial port and TCP server details:

```json
{
    "serial_port": "/dev/ttyUSB0",     // Your serial port
    "serial_baudrate": 9600,            // Match your device
    "tcp_host": "localhost",            // Your TCP server
    "tcp_port": 5000                    // Your TCP port
}
```

### 3. Start the Application

**Option A: Using the startup script**
```bash
./start.sh
```

**Option B: Manual start**
```bash
python3 web_service.py
```

Then open your browser: **http://localhost:8080**

---

## Testing Without Hardware

### Step 1: Start the Test TCP Server

In one terminal:
```bash
python3 test_tcp_server.py
```

This starts a TCP server on port 5000 that will display received data.

### Step 2: Start the Web Service

In another terminal:
```bash
python3 web_service.py
```

### Step 3: Configure and Test

1. Open http://localhost:8080 in your browser
2. Configure your serial port settings
3. Make sure TCP host is `localhost` and port is `5000`
4. Click "Start Service"
5. Watch the test server receive data from your serial port!

---

## Common Serial Ports

| Operating System | Common Serial Ports |
|------------------|---------------------|
| Linux | `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/ttyS0` |
| macOS | `/dev/cu.usbserial`, `/dev/tty.usbserial` |
| Windows | `COM1`, `COM2`, `COM3`, etc. |

To list available serial ports on Linux:
```bash
ls /dev/tty*
```

---

## Web Interface Features

✅ **Real-time Status Monitoring**
- Service status (Running/Stopped)
- Serial port connection status
- TCP connection status
- Live statistics

✅ **Full Configuration**
- Serial port settings (port, baud rate, parity, etc.)
- TCP server settings (host, port)
- Buffer size and reconnection interval

✅ **Buffer Management**
- View buffered messages
- See buffer size and statistics
- Clear buffer when needed

✅ **Service Control**
- Start/Stop the forwarding service
- Apply configuration changes on-the-fly
- View error messages

---

## Troubleshooting

### "Permission denied" on serial port (Linux)

```bash
sudo usermod -a -G dialout $USER
# Log out and log back in
```

### Can't find serial port

List all serial devices:
```bash
# Linux
ls -l /dev/tty*

# macOS
ls -l /dev/cu.*

# Or use Python
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

### TCP connection refused

Make sure your TCP server is running and the firewall allows the connection.

Test with netcat:
```bash
nc -l 5000  # Start a simple TCP server
```

---

## What Happens When Connection is Lost?

1. **Serial port disconnected**: 
   - Automatically attempts to reconnect every 5 seconds
   - No data is lost if TCP is still connected

2. **TCP connection lost**:
   - Incoming serial data is buffered in memory
   - Attempts to reconnect every 5 seconds
   - Once reconnected, all buffered data is sent automatically

---

## Need Help?

Check the main [README.md](README.md) for detailed documentation.
