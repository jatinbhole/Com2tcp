# Setup Instructions for Python 3.8

## Quick Start with Python 3.8

### Step 1: Install Python 3.8
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.8 python3.8-venv python3.8-dev

# macOS (with Homebrew)
brew install python@3.8

# Windows
# Download from https://www.python.org/downloads/release/python-3810/
```

### Step 2: Create Virtual Environment with Python 3.8
```bash
# Navigate to project directory
cd /workspaces/Com2tcp

# Remove existing venv if it uses wrong Python
rm -rf .venv

# Create fresh venv with Python 3.8
python3.8 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### Step 3: Verify Python Version
```bash
python --version
# Should output: Python 3.8.x
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run the Service
```bash
python service_runner.py
```

## Using pyenv (Recommended for Multiple Python Versions)

### Install pyenv
```bash
# macOS
brew install pyenv

# Linux
curl https://pyenv.run | bash

# Add to shell configuration (.bashrc, .zshrc, etc.)
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
```

### Set Up Python 3.8 with pyenv
```bash
# Install Python 3.8
pyenv install 3.8.10

# Set local version for this project
cd /workspaces/Com2tcp
pyenv local 3.8.10

# Verify
python --version  # Should show Python 3.8.10
```

### Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Using conda

### Create Conda Environment
```bash
# Create environment with Python 3.8
conda create -n com2tcp python=3.8

# Activate
conda activate com2tcp

# Install dependencies
pip install -r requirements.txt
```

## Docker Setup (Recommended for Consistency)

Create a `Dockerfile`:
```dockerfile
FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Verify Python version
RUN python --version

EXPOSE 8080

CMD ["python", "service_runner.py"]
```

Build and run:
```bash
docker build -t com2tcp:py38 .
docker run -p 8080:8080 com2tcp:py38
```

## Troubleshooting Python 3.8 Setup

### Issue: "command not found: python3.8"
**Solutions:**
1. Install Python 3.8 for your system (see Step 1 above)
2. Or use the system Python with explicit path:
   ```bash
   /usr/bin/python3.8 -m venv .venv
   ```

### Issue: "Error: Python 3.8 only is required"
**Solutions:**
1. Verify active Python: `python --version`
2. Check venv is activated: `which python` (should show .venv)
3. Create new venv with explicit Python 3.8:
   ```bash
   rm -rf .venv
   python3.8 -m venv .venv
   source .venv/bin/activate
   ```

### Issue: pip install fails
**Solutions:**
1. Upgrade pip: `pip install --upgrade pip`
2. Clear pip cache: `pip cache purge`
3. Install with verbose output: `pip install -v -r requirements.txt`

### Issue: Service won't start
**Solutions:**
1. Check Python version: `python --version` (must be 3.8.x)
2. Verify dependencies: `pip list | grep Flask`
3. Check imports: `python -c "from serial_forwarder import MultiPortForwarder"`

## Environment Variables (Optional)

```bash
# Set secret key for Flask (production only)
export SECRET_KEY="your-secure-secret-key-here"

# Set log level (optional)
export LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR

# Set port (optional)
export PORT="8080"
```

## Running as a Service

### systemd Service File
Create `/etc/systemd/system/com2tcp.service`:
```ini
[Unit]
Description=Serial to TCP Forwarder Service
After=network.target

[Service]
Type=simple
User=com2tcp
WorkingDirectory=/opt/com2tcp
ExecStart=/opt/com2tcp/.venv/bin/python service_runner.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable com2tcp
sudo systemctl start com2tcp
sudo systemctl status com2tcp
```

## Verification Checklist

- [ ] Python 3.8 installed: `python --version` → 3.8.x
- [ ] Virtual environment created with Python 3.8
- [ ] Virtual environment activated
- [ ] Dependencies installed: `pip list`
- [ ] Can import modules: `python -c "import serial_forwarder"`
- [ ] Service runs: `python service_runner.py` (starts without version error)
- [ ] Web interface accessible: http://localhost:8080
- [ ] Can login with admin/admin123

## Next Steps

Once setup is complete:
1. See [AUTHENTICATION.md](AUTHENTICATION.md) for login and password management
2. See [README.md](README.md) for feature documentation
3. See [PYTHON_VERSION.md](PYTHON_VERSION.md) for Python 3.8 requirement details
