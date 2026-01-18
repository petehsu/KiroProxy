# Server Deployment Guide

This guide covers deploying Kiro Proxy on various server environments.

## Table of Contents

- [Option 1: Pre-built Binary (Recommended)](#option-1-pre-built-binary-recommended)
- [Option 2: Run from Source](#option-2-run-from-source)
- [Option 3: Docker Deployment](#option-3-docker-deployment)
- [Account Configuration](#account-configuration)
- [Auto-start on Boot](#auto-start-on-boot)
- [Reverse Proxy Setup](#reverse-proxy-setup)

---

## Option 1: Pre-built Binary (Recommended)

Simplest method, no dependencies required.

### Linux (x86_64)

```bash
# Download latest version
wget https://github.com/petehsu/KiroProxy/releases/latest/download/KiroProxy-1.7.1-linux-x86_64

# Add execute permission
chmod +x KiroProxy-1.7.1-linux-x86_64

# Run
./KiroProxy-1.7.1-linux-x86_64

# Specify port
./KiroProxy-1.7.1-linux-x86_64 8081
```

### macOS

```bash
# Intel Mac
curl -LO https://github.com/petehsu/KiroProxy/releases/latest/download/KiroProxy-1.7.1-macos-x86_64
chmod +x KiroProxy-1.7.1-macos-x86_64
./KiroProxy-1.7.1-macos-x86_64

# If prompted about unverified developer:
xattr -d com.apple.quarantine KiroProxy-1.7.1-macos-x86_64
```

### Windows

```powershell
# PowerShell download
Invoke-WebRequest -Uri "https://github.com/petehsu/KiroProxy/releases/latest/download/KiroProxy-1.7.1-windows-x86_64.exe" -OutFile "KiroProxy.exe"

# Run
.\KiroProxy.exe
```

---

## Option 2: Run from Source

Requires Python 3.9+ and Git.

```bash
# Clone project
git clone https://github.com/petehsu/KiroProxy.git
cd KiroProxy

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python run.py

# Specify port
python run.py 8081
```

### Update to Latest Version

```bash
cd KiroProxy
git pull origin main
pip install -r requirements.txt
```

---

## Option 3: Docker Deployment

### Using Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

VOLUME ["/root/.config/kiro-proxy"]

CMD ["python", "run.py"]
```

Build and run:

```bash
docker build -t kiro-proxy .
docker run -d -p 8080:8080 -v kiro-data:/root/.config/kiro-proxy --name kiro-proxy kiro-proxy
```

---

## Account Configuration

Servers usually don't have browsers. Several ways to add accounts:

### Option 1: Remote Login Link (Recommended)

1. Start KiroProxy on server
2. Open `http://server-ip:8080` in local browser
3. Click "Remote Login Link" button
4. Copy generated link, open in local browser
5. Complete Google/GitHub authorization
6. Account auto-added to server

### Option 2: Import/Export

**On local computer:**
```bash
# Run KiroProxy and login
python run.py

# Export accounts
python run.py accounts export -o accounts.json
```

**On server:**
```bash
# Upload accounts.json then import
python run.py accounts import accounts.json
```

### Option 3: Manual Add Token

1. Login in local Kiro IDE
2. Find JSON files in `~/.aws/sso/cache/` directory
3. Copy `accessToken` and `refreshToken`

**On server:**
```bash
# Interactive add
python run.py accounts add
```

---

## Auto-start on Boot

### Linux (systemd)

Create `/etc/systemd/system/kiro-proxy.service`:

```ini
[Unit]
Description=Kiro API Proxy
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kiro-proxy
ExecStart=/opt/kiro-proxy/KiroProxy
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable kiro-proxy
sudo systemctl start kiro-proxy

# Check status
sudo systemctl status kiro-proxy

# View logs
sudo journalctl -u kiro-proxy -f
```

### Linux (screen/tmux)

```bash
# Using screen
screen -S kiro
./KiroProxy
# Press Ctrl+A D to detach

# Reattach
screen -r kiro
```

### Windows (Task Scheduler)

```powershell
# Create scheduled task (auto-start on boot)
$action = New-ScheduledTaskAction -Execute "C:\KiroProxy\KiroProxy.exe"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount
Register-ScheduledTask -TaskName "KiroProxy" -Action $action -Trigger $trigger -Principal $principal

# Start immediately
Start-ScheduledTask -TaskName "KiroProxy"
```

---

## Reverse Proxy Setup

### Nginx

```nginx
server {
    listen 80;
    server_name kiro.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }
}
```

**Enable HTTPS (using Certbot):**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d kiro.example.com
```

### Caddy

```caddyfile
kiro.example.com {
    reverse_proxy localhost:8080
}
```

Caddy auto-manages HTTPS certificates.

---

## Common Issues

### Port in Use

```bash
# Check port usage
lsof -i :8080  # Linux/macOS
netstat -ano | findstr :8080  # Windows

# Use different port
./KiroProxy 8081
```

### Firewall Configuration

**Ubuntu/Debian (ufw):**
```bash
sudo ufw allow 8080/tcp
```

**CentOS/RHEL (firewalld):**
```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

**Windows:**
```powershell
New-NetFirewallRule -DisplayName "KiroProxy" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow
```

### View Logs

```bash
# systemd
sudo journalctl -u kiro-proxy -f

# Direct run
./KiroProxy 2>&1 | tee kiro.log
```
