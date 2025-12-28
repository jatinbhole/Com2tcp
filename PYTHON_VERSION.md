# Python 3.8 Requirement

## Overview
This project **requires Python 3.8 and is not compatible with Python 3.9 or higher**.

## Why Python 3.8 Only?
- ✅ Stable and proven platform
- ✅ All dependencies are optimized for 3.8
- ✅ Ensures consistent behavior across all deployments
- ✅ Avoids compatibility issues with newer Python versions

## Version Enforcement

The application enforces Python 3.8 at multiple points:

### 1. **Runtime Check** (Primary)
All three main modules check the Python version at startup:
- `service_runner.py` - Main service entry point
- `serial_forwarder.py` - Serial port forwarder module
- `web_service.py` - Flask web service

If Python version is not 3.8:
```
Error: Python 3.8 only is required
Current version: <your-version>
```

### 2. **.python-version** File
The `.python-version` file specifies `3.8.0` for tools like `pyenv`:
```
3.8.0
```

### 3. **Requirements.txt**
Locked dependency versions are compatible with Python 3.8:
```
Flask==3.0.0
Flask-Login==0.6.3
pyserial==3.5
```

## Installation with Python 3.8

### Using pyenv (Recommended)
```bash
# Install pyenv
curl https://pyenv.run | bash

# Install Python 3.8
pyenv install 3.8.10

# Activate in project directory
pyenv shell 3.8.10
```

### Using venv with Python 3.8
```bash
# Create virtual environment with Python 3.8
python3.8 -m venv .venv

# Activate
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Using conda
```bash
# Create environment with Python 3.8
conda create -n com2tcp python=3.8

# Activate
conda activate com2tcp
```

## Version Check Command
Verify Python version before running:
```bash
python --version
# Output should be: Python 3.8.x
```

## Troubleshooting

### Error: "Python 3.8 only is required"
**Solution**: You have Python 3.9+ installed. Switch to Python 3.8:
```bash
# With pyenv
pyenv shell 3.8.10

# With venv
python3.8 -m venv .venv
source .venv/bin/activate
```

### Error: "python3.8: command not found"
**Solution**: Install Python 3.8:
- Ubuntu/Debian: `sudo apt-get install python3.8`
- macOS: `brew install python@3.8`
- Windows: Download from python.org

### Service Fails to Start
1. Check Python version: `python --version`
2. Verify it's 3.8.x (not 3.9+)
3. Check virtual environment is activated
4. Reinstall requirements: `pip install -r requirements.txt`

## Features by Python Version

| Feature | Python 3.8 | Python 3.9+ |
|---------|-----------|-----------|
| Serial Forwarding | ✅ Supported | ❌ Not Supported |
| Multi-Port Support | ✅ Supported | ❌ Not Supported |
| Web Interface | ✅ Supported | ❌ Not Supported |
| Authentication | ✅ Supported | ❌ Not Supported |
| SQLite Buffering | ✅ Supported | ❌ Not Supported |
| API Endpoints | ✅ Supported | ❌ Not Supported |

## Migration Notes

If you have Python 3.9+ installed:

1. **Do NOT upgrade** - The application won't run
2. **Install Python 3.8 alongside** your current version
3. **Use 3.8 for this project** - Other projects can use newer versions
4. **Consider multi-version setup** with pyenv or conda for flexibility

## Future Python Support

Currently no plans to upgrade to Python 3.9+. The project is optimized and tested for Python 3.8 only.

For questions about Python compatibility, refer to `AUTHENTICATION.md` for additional configuration details.
