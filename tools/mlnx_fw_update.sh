#!/bin/bash

# Create a temporary directory for downloads
TEMP_DIR=$(mktemp -d)

# Function to clean up the temporary directory
cleanup() {
  rm -rf "$TEMP_DIR"
}

# Trap to ensure cleanup on script exit
trap cleanup EXIT

# Download the firmware file
wget -P "$TEMP_DIR" https://content.mellanox.com/firmware/fw-ConnectX5-rel-16_35_4030-MCX555A-ECA_Ax_Bx-UEFI-14.29.15-FlexBoot-3.6.902.bin.zip
if [ $? -ne 0 ]; then
  echo "Failed to download the firmware file."
  exit 1
fi

# Unzip the firmware file
unzip "$TEMP_DIR/fw-ConnectX5-rel-16_35_4030-MCX555A-ECA_Ax_Bx-UEFI-14.29.15-FlexBoot-3.6.902.bin.zip" -d "$TEMP_DIR"
if [ $? -ne 0 ]; then
  echo "Failed to unzip the firmware file."
  exit 1
fi

# Burn the firmware and restart
mstflint -d 02:00.0 -i "$TEMP_DIR/fw-ConnectX5-rel-16_35_4030-MCX555A-ECA_Ax_Bx-UEFI-14.29.15-FlexBoot-3.6.902.bin" burn
if [ $? -ne 0 ]; then
  echo "Failed to burn the firmware."
  exit 1
fi

# Reboot the system
reboot now
