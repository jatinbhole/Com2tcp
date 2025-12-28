# Installation and Setup Guide

## Single Systemd Service Setup

The unified service runs both the **Web Service** and **Serial Forwarder** from a single systemd service.

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/jatinbhole/Com2tcp.git
   cd Com2tcp
   ```

2. **Create Python virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the service file**
   
   Edit `serial-forwarder.service` and update these values:
   - `User=` - Set to your username (or `root` for system-wide)
   - `WorkingDirectory=` - Set to your Com2tcp directory path
   - `ExecStart=` - Set to your venv Python path
   
   Example:
   ```ini
   User=ubuntu
   WorkingDirectory=/home/ubuntu/Com2tcp
   ExecStart=/home/ubuntu/Com2tcp/venv/bin/python /home/ubuntu/Com2tcp/service_runner.py
   ```

5. **Install the systemd service**
   ```bash
   sudo cp serial-forwarder.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

6. **Update your configuration**
   
   Edit `config.json` to configure your serial ports and TCP destinations:
   ```json
   {
       "ports": [
           {
               "name": "port1",
               "serial_port": "/dev/ttyUSB0",
               "serial_baudrate": 9600,
               "serial_bytesize": 8,
               "serial_parity": "N",
               "serial_stopbits": 1,
               "serial_timeout": 1,
               "serial_xonxoff": true,
               "serial_rtscts": false,
               "tcp_host": "localhost",
               "tcp_port": 5000,
               "buffer_size": 10000,
               "reconnect_interval": 5
           }
       ]
   }
   ```

### Running the Service

**Start the service:**
```bash
sudo systemctl start serial-forwarder
```

**Enable at boot:**
```bash
sudo systemctl enable serial-forwarder
```

**Check status:**
```bash
sudo systemctl status serial-forwarder
```

**View logs:**
```bash
sudo journalctl -u serial-forwarder -f
```

**Stop the service:**
```bash
sudo systemctl stop serial-forwarder
```

**Restart the service:**
```bash
sudo systemctl restart serial-forwarder
```

## Service Components

### 1. Serial Forwarder (`serial_forwarder.py`)
- Runs in background
- Manages multiple serial ports independently
- Each port has its own:
  - Serial connection handler
  - TCP connection manager
  - SQLite buffer storage
  - Automatic reconnection logic
- Features:
  - Xon/Xoff software flow control
  - RTS/CTS hardware flow control toggle
  - Persistent buffering with SQLite
  - Multi-threaded operation

### 2. Web Service (`web_service.py`)
- Flask-based REST API
- Runs on port 8080
- Endpoints:
  - `GET /` - Web dashboard
  - `GET /api/status` - Current status
  - `GET /api/config` - Current configuration
  - `POST /api/config` - Update configuration
  - `POST /api/start` - Start forwarder
  - `POST /api/stop` - Stop forwarder
  - `GET /api/buffer` - Buffer information
  - `POST /api/clear_buffer` - Clear buffer

### 3. Service Runner (`service_runner.py`)
- Unified entry point
- Starts both services in parallel
- Handles graceful shutdown
- Manages signal handling (SIGTERM, SIGINT)

## Configuration

### Serial Port Settings
- `serial_port` - Device path (e.g., `/dev/ttyUSB0`)
- `serial_baudrate` - Baud rate (e.g., 9600, 115200)
- `serial_bytesize` - Data bits (5-8)
- `serial_parity` - N (None), E (Even), O (Odd)
- `serial_stopbits` - Stop bits (1 or 2)
- `serial_timeout` - Read timeout in seconds
- `serial_xonxoff` - Enable Xon/Xoff flow control (true/false)
- `serial_rtscts` - Enable RTS/CTS flow control (true/false)

### TCP Settings
- `tcp_host` - Target host/IP
- `tcp_port` - Target port

### Buffer Settings
- `buffer_size` - Maximum buffered messages
- `reconnect_interval` - Reconnection attempt interval (seconds)

## Troubleshooting

### Service won't start
- Check the service file paths are correct
- Verify Python interpreter path
- Check file permissions
- View logs: `sudo journalctl -u serial-forwarder`

### Can't connect to serial port
- Ensure device exists: `ls -l /dev/ttyUSB*`
- Check user permissions: `id` and group membership
- Verify USB device is powered and connected

### TCP connection refused
- Verify target server is running and listening
- Check firewall rules
- Confirm correct host/port in config

### Buffer not persisting
- Check SQLite database files exist
- Verify directory permissions: `ls -l buffers/`
- Check disk space available

## Uninstalling

```bash
sudo systemctl stop serial-forwarder
sudo systemctl disable serial-forwarder
sudo rm /etc/systemd/system/serial-forwarder.service
sudo systemctl daemon-reload
```

## Security Notes

- Change the Flask secret key in `web_service.py`
- Consider using firewall to restrict Web Service access
- Run service with minimal required privileges
- Keep Python and dependencies updated
