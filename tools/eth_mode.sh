#!/bin/bash

if [ -z "$1" ]; then
	echo "Usage: $0 <XX:XX.X>
	exit 1
fi 

PCIE=$1

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run with superuser privileges (sudo)."
  exit 1
fi

if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ $ID == "ubuntu" || $ID == "debian" ]]; then
        TMP=$(mktemp -d)

        cleanup() {
            rm -rf "$TMP"
        }

        trap cleanup EXIT

        wget -P "$TMP" https://www.mellanox.com/downloads/MFT/mft-4.30.1-113-x86_64-deb.tgz
        if [ $? -ne 0 ]; then
            echo "Failed to download mft file"
            exit 1
        fi

	tar -xf "$TMP/mft-4.30.1-113-x86_64-deb.tgz" -C "$TMP"
	if [ $? -ne 0 ]; then
		echo "Failed to extract archive"
		exit 1
	fi
	
	yes | apt-get update -y
	yes | apt-get install -y gcc make dkms linux-headers-$(uname -r)

	yes | $TMP/install.sh
	if [ $? -ne 0 ]; then
		echo "Failed to install MFT"
		exit 1
	fi
	
	yes | mlxconfig -d $PCIE set LINK_TYPE_P1=2 -y
	if [ $? -ne 0 ]; then
		echo "Error while changing configuration"
		exit 1
	fi

        echo "Download completed successfully. Rebooting now..."
        reboot now
    else
        echo "The operating system is not Ubuntu or Debian."
        exit 1
    fi
else
    echo "/etc/os-release file not found."
    exit 1
fi
