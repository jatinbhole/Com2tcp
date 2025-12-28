# Authentication System Documentation

## Overview
The Serial to TCP Forwarder service now includes a complete authentication system with login, logout, and password management features.

## Features Implemented

### 1. Login System
- **Login Page**: Secure login page at `/login` with username and password fields
- **Session Management**: Flask-Login integration for persistent user sessions
- **Default Credentials**: 
  - Username: `admin`
  - Password: `admin123`
- **Redirect Protection**: Unauthenticated users are automatically redirected to login page

### 2. Credentials Management
- **Secure Storage**: Passwords are hashed using `werkzeug.security.generate_password_hash()`
- **Persistent Storage**: Credentials stored in `credentials.json` file
- **Automatic Initialization**: System creates default credentials on first run

### 3. Password Change Feature
- **Secure Endpoint**: `/api/change_password` protected with `@login_required`
- **Validation Rules**:
  - Old password must be verified before change
  - New password must be at least 6 characters
  - Password confirmation must match new password
- **User Interface**: 
  - "🔐 Change Password" button in dashboard header
  - Modal dialog for password change
  - Real-time validation feedback

### 4. Logout Feature
- **Logout Route**: `/logout` endpoint with session cleanup
- **UI Button**: "🚪 Logout" button in dashboard header
- **Session Cleanup**: Properly clears user session

## Architecture

### Authentication Flow
```
User Request
    ↓
Check Session Cookie
    ↓
Valid? → Show Dashboard
    ↓
Invalid? → Redirect to /login
    ↓
POST username/password
    ↓
Verify Credentials
    ↓
Valid? → Create Session → Show Dashboard
    ↓
Invalid? → Show Error → Redirect to /login
```

### Protected Routes
- `/` - Main dashboard (requires login)
- `/api/status` - Status API (requires login)
- `/api/buffer` - Buffer API (requires login)
- `/api/config` - Configuration API (requires login)
- `/api/port/*` - Port control endpoints (require login)
- `/api/change_password` - Password change endpoint (requires login)

### Public Routes
- `/login` - Login page (no authentication required)

## Security Features

### Password Security
- **Hashing**: Passwords hashed with werkzeug.security using pbkdf2:sha256
- **No Plain Text**: Credentials file stores only hashed passwords
- **Session Cookies**: Secure session management with Flask-Login
- **HTTPS Ready**: Configure `SECRET_KEY` environment variable for production

### Session Management
- **Remember Me**: Login form includes "remember me" option for persistent sessions
- **Session Timeout**: Can be configured in production environment
- **User Isolation**: Each user session is isolated and secure

## File Structure

### New/Modified Files

**web_service.py**
- Added Flask-Login integration
- Added User model class
- Added login/logout routes
- Added password change endpoint
- Protected dashboard routes

**templates/login.html** (New)
- Professional login page with gradient background
- Demo credentials display
- Error message handling
- Responsive design for mobile devices

**templates/index_multi.html** (Modified)
- Added username display in header
- Added "Change Password" button with modal
- Added "Logout" button
- Added password change modal dialog
- Added JavaScript for modal management

**requirements.txt** (Modified)
- Added Flask-Login==0.6.3 dependency

**credentials.json** (Auto-created)
- Stores hashed credentials
- Auto-created on first run with default admin account

## Testing the Authentication System

### 1. Start the Service
```bash
cd /workspaces/Com2tcp
python service_runner.py
```

### 2. Access Login Page
Navigate to: `http://localhost:8080/login`

### 3. Login with Default Credentials
- Username: `admin`
- Password: `admin123`

### 4. Change Password
1. Click "🔐 Change Password" button in dashboard
2. Enter current password (admin123)
3. Enter new password (minimum 6 characters)
4. Confirm new password
5. Click "Change Password"

### 5. Logout
Click "🚪 Logout" button in dashboard header

## Configuration

### Environment Variables (Optional)
```bash
export SECRET_KEY="your-secure-secret-key"
```

### Production Deployment
For production:
1. Change `SECRET_KEY` environment variable
2. Use HTTPS/SSL
3. Implement session timeout
4. Regular credential backups
5. Audit logging

## Default Credentials
On first run, the system creates:
- **Username**: admin
- **Password**: admin123

**⚠️ IMPORTANT**: Change the default password immediately after first login!

## Dependencies
- Flask==3.0.0 (Web framework)
- Flask-Login==0.6.3 (Authentication)
- pyserial==3.5 (Serial communication)
- werkzeug (Password hashing - included with Flask)

## Troubleshooting

### Issue: "Invalid username or password" error
**Solution**: Verify credentials.json exists and contains valid hashed passwords

### Issue: Login page not appearing
**Solution**: Ensure Flask-Login is installed: `pip install Flask-Login==0.6.3`

### Issue: Session expires immediately
**Solution**: Check SECRET_KEY is set in environment or using default

### Issue: Password change modal not working
**Solution**: Check browser console for errors, verify JavaScript is enabled

## Future Enhancements
- [ ] User registration system
- [ ] Password reset via email
- [ ] Two-factor authentication
- [ ] User roles and permissions
- [ ] Audit logging
- [ ] Session management UI
- [ ] Password complexity requirements
- [ ] Account lockout after failed attempts
