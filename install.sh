#!/bin/bash

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
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
    espeak-data

# Install Python packages
pip3 install -r requirements.txt --break-system-packages

# Set up audio (may need to configure based on your audio setup)
sudo amixer cset numid=3 1  # Force audio output to 3.5mm jack if needed

echo "Installation complete. Please configure your AWS credentials and database settings."
