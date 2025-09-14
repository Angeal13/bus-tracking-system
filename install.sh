#!/bin/bash

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
sudo apt-get install -y python3-pip python3-dev libsdl2-mixer-2.0-0 libsdl2-image-2.0-0 libsdl2-2.0-0 mariadb-server mariadb-client
# Install MariaDB client libraries
sudo apt-get install -y libmariadb3 libmariadb-dev

# Install Python packages
pip3 install -r requirements.txt --break-system-packages

# Setup audio (if needed)
sudo usermod -a -G audio pi

echo "Installation complete. Please reboot if this is the first installation."
