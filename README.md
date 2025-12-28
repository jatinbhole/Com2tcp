# Serial Port to TCP Forwarder

A robust Python application that forwards data from a serial port to a TCP connection with automatic buffering when the connection is lost. Includes a web-based control panel for configuration and monitoring.

## Features

- 🔌 **Serial to TCP Forwarding**: Forward data from any serial port to a TCP endpoint
- 📦 **Automatic Buffering**: Store data in a buffer when TCP connection is lost
- � **Persistent Buffer**: Buffer is saved to disk and survives service restarts
- �🔄 **Auto-Reconnect**: Automatically reconnects to both serial port and TCP server
- 🌐 **Web Interface**: Beautiful web-based control panel for configuration and monitoring
- 📊 **Real-time Monitoring**: Live status updates and statistics
- ⚙️ **Flexible Configuration**: Configure all serial and TCP parameters via web UI
- 🛡️ **Thread-Safe**: Robust multi-threaded design with proper locking

## Requirements

- Python 3.7+
- Serial port (e.g., `/dev/ttyUSB0`, `COM1`, etc.)
- Target TCP server

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Com2tcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.json` to set your default configuration:

```json
{
    "serial_port": "/dev/ttyUSB0",
    "serial_baudrate": 9600,
    "serial_bytesize": 8,
    "serial_parity": "N",
    "serial_stopbits": 1,
    "serial_timeout": 1,
    "tcp_host": "localhost",
    "tcp_port": 5000,
    "buffer_size": 10000,
    "reconnect_interval": 5
}
```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serial_port` | Serial port device path | `/dev/ttyUSB0` |
| `serial_baudrate` | Baud rate (300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600) | `9600` |
| `serial_bytesize` | Data bits (5, 6, 7, 8) | `8` |
| `serial_parity` | Parity (N=None, E=Even, O=Odd) | `N` |
| `serial_stopbits` | Stop bits (1, 2) | `1` |
| `serial_timeout` | Read timeout in seconds | `1` |
| `tcp_host` | TCP server hostname or IP | `localhost` |
| `tcp_port` | TCP server port | `5000` |
| `buffer_size` | Maximum buffer size (messages) | `10000` |
| `reconnect_interval` | Reconnection attempt interval (seconds) | `5` |

## Usage

### Option 1: Web Service with Control Panel (Recommended)

Start the Flask web service:

```bash
python web_service.py
```

Then open your browser and navigate to:
```
http://localhost:8080
```

From the web interface you can:
- Start/Stop the forwarding service
- Configure all serial and TCP parameters
- Monitor connection status in real-time
- View statistics (messages sent, buffered, etc.)
- View and clear the buffer
- See error messages

### Option 2: Standalone Mode

Run the forwarder directly:

```bash
python serial_forwarder.py
```

Press `Ctrl+C` to stop.

## How It Works

1. **Serial Reading**: The application continuously reads data from the configured serial port
2. **TCP Forwarding**: Data is immediately forwarded to the TCP server when connected
3. **Buffering**: If the TCP connection is lost, incoming serial data is stored in a buffer
4. **Persistent Storage**: Buffer is automatically saved to disk (`buffer.pkl`) for persistence across restarts
5. **Auto-Recovery**: The application automatically attempts to reconnect to the TCP server
6. **Buffer Flush**: Once reconnected, all buffered data (including data from previous sessions) is sent to the TCP server
7. **Automatic Cleanup**: Buffer file is removed automatically when all data is successfully sent

## Web API Endpoints

The Flask service provides the following REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get current status and statistics |
| `/api/config` | GET | Get current configuration |
| `/api/config` | POST | Update configuration |
| `/api/start` | POST | Start the forwarder |
| `/api/stop` | POST | Stop the forwarder |
| `/api/buffer` | GET | Get buffer information |
| `/api/clear_buffer` | POST | Clear the buffer |

## Example API Usage

### Get Status
```bash
curl http://localhost:8080/api/status
```

### Update Configuration
```bash
curl -X POST http://localhost:8080/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "serial_port": "/dev/ttyUSB0",
    "serial_baudrate": 115200,
    "tcp_host": "192.168.1.100",
    "tcp_port": 8000
  }'
```

### Start Service
```bash
curl -X POST http://localhost:8080/api/start
```

## Troubleshooting

### Serial Port Permission Denied

On Linux, add your user to the dialout group:
```bash
sudo usermod -a -G dialout $USER
```
Then log out and log back in.

### TCP Connection Refused

- Ensure your TCP server is running and accessible
- Check firewall settings
- Verify the host and port in configuration

### Buffer Filling Up

- Check if your TCP server is accepting connections
- Increase `buffer_size` in configuration if needed
- Clear the buffer via the web interface

## Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│ Serial Port │ ──────> │ Serial Forwarder │ ──────> │ TCP Server  │
└─────────────┘         │   (with buffer)  │         └─────────────┘
                        └──────────────────┘
                               │
                               │
                        ┌──────▼──────┐
                        │ Flask Web   │
                        │ Service     │
                        │ (Port 8080) │
                        └─────────────┘
```

## Development

The project consists of three main components:

1. **serial_forwarder.py**: Core forwarding logic with buffering
2. **web_service.py**: Flask web service and REST API
3. **templates/index.html**: Web-based control panel UI

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.
