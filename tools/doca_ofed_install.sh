#!/bin/bash

# Function to clean up the temporary directory
cleanup() {
  rm -rf "$TEMP_DIR"
}

# Trap to ensure cleanup on script exit
trap cleanup EXIT

# Update the system
yes | dnf update -y
if [ $? -ne 0 ]; then
  echo "Failed to update the system."
  exit 1
fi

# Install dependencies
yes | dnf install -y cpan gcc-gfortran tk
if [ $? -ne 0 ]; then
  echo "Failed to install dependencies."
  exit 1
fi

# Create a temporary directory for downloads
TEMP_DIR=$(mktemp -d)

# Download drivers to the temporary directory
wget -P "$TEMP_DIR" https://www.mellanox.com/downloads/DOCA/DOCA_v2.10.0/host/doca-host-2.10.0-093000_25.01_rhel95.x86_64.rpm
if [ $? -ne 0 ]; then
  echo "Failed to download the drivers."
  exit 1
fi

# Install drivers
yes | rpm -i $TEMP_DIR/doca-host-2.10.0-093000_25.01_rhel95.x86_64.rpm
if [ $? -ne 0 ]; then
  echo "Failed to install the drivers."
  exit 1
fi

# Cleaning tmp files and unused deps
yes | dnf clean all
if [ $? -ne 0 ]; then
  echo "Failed to clean tmp files."
  exit 1
fi

# Installing DOCA-OFED
yes | dnf install doca-ofed --skip-broken
if [ $? -ne 0 ]; then
  echo "Failed to install ofed drivers."
  exit 1
fi


