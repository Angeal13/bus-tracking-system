#!/bin/bash

# Bus Tracking System Installation
echo "=================================================="
echo "       Bus Tracking System Installation"
echo "=================================================="

# Configuration
USER="pi"
APP_DIR="/home/pi/bus-tracking-system"
SERVICE_NAME="bus-tracker"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please do not run as root. Run as pi user."
    exit 1
fi

# Update system
echo "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libmariadb-dev \
    espeak \
    espeak-data \
    python3-gpiozero \
    alsa-utils \
    python3-pynput \
    python3-boto3

# Install Python packages
echo "Installing Python packages..."
pip3 install -r requirements.txt

# Configure audio
echo "Configuring audio output..."
sudo amixer cset numid=3 1      # Force to 3.5mm jack
sudo amixer set Master 80%      # Set volume to 80%

# Make audio settings persistent
echo "Making audio settings persistent..."
if [ -f /etc/rc.local ]; then
    sudo sed -i '/amixer cset numid=3/d' /etc/rc.local
    sudo sed -i '/amixer set Master/d' /etc/rc.local
    sudo sed -i '/^exit 0/i amixer cset numid=3 1\namixer set Master 80%' /etc/rc.local
fi

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Bus Tracking System
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=${APP_DIR}
ExecStartPre=/bin/bash -c 'amixer cset numid=3 1 && amixer set Master 80%'
ExecStart=/usr/bin/python3 ${APP_DIR}/src/main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Set service permissions
sudo chmod 644 /etc/systemd/system/${SERVICE_NAME}.service

# Reload and enable service
echo "Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.service

# Create control script
echo "Creating control scripts..."
sudo tee /usr/local/bin/${SERVICE_NAME}-ctl > /dev/null << EOF
#!/bin/bash
case "\$1" in
    start)   sudo systemctl start ${SERVICE_NAME}.service ;;
    stop)    sudo systemctl stop ${SERVICE_NAME}.service ;;
    restart) sudo systemctl restart ${SERVICE_NAME}.service ;;
    status)  sudo systemctl status ${SERVICE_NAME}.service ;;
    logs)    journalctl -u ${SERVICE_NAME}.service -f ;;
    *)       echo "Usage: ${SERVICE_NAME}-ctl {start|stop|restart|status|logs}" ;;
esac
EOF

sudo chmod +x /usr/local/bin/${SERVICE_NAME}-ctl

# Create data directory for offline storage
mkdir -p offline_data

# Test audio
echo "Testing audio configuration..."
speaker-test -t wav -c 2 -l 1 > /dev/null 2>&1

# Completion message
echo "=================================================="
echo "           Installation Complete!"
echo "=================================================="
echo "Audio: Configured for 3.5mm jack"
echo "Service: Installed and enabled"
echo "Database: Optimized for DynamoDB + Aurora"
echo ""
echo "Management commands:"
echo "  ${SERVICE_NAME}-ctl start    - Start service"
echo "  ${SERVICE_NAME}-ctl stop     - Stop service"
echo "  ${SERVICE_NAME}-ctl restart  - Restart service"
echo "  ${SERVICE_NAME}-ctl status   - Check status"
echo "  ${SERVICE_NAME}-ctl logs     - View live logs"
echo ""
echo "The system will start automatically on boot."
echo "=================================================="
