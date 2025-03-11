#!/bin/bash

# Function to clean up the temporary directory
cleanup() {
  rm -rf "$TEMP_DIR"
}

# Trap to ensure cleanup on script exit
#trap cleanup EXIT

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
wget -P "$TEMP_DIR" https://content.mellanox.com/ofed/MLNX_OFED-24.10-2.1.8.0/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz
if [ $? -ne 0 ]; then
  echo "Failed to download the drivers."
  exit 1
fi

# Extract the drivers
tar -xf "$TEMP_DIR/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz" -C "$TEMP_DIR"
if [ $? -ne 0 ]; then
  echo "Failed to extract the drivers."
  exit 1
fi

# Install drivers
yes | "$TEMP_DIR/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64/mlnxofedinstall --without-fw-update"
if [ $? -ne 0 ]; then
  echo "Failed to install the drivers."
  exit 1
fi

# Create autoload kernel module
echo ib_ipoib | tee -a /etc/modules-load.d/ib_ipoib.conf
if [ $? -ne 0 ]; then
  echo "Failed to create autoload kernel module configuration."
  exit 1
fi

# Reboot the system
reboot now
