#!/bin/bash

# Update the system
dnf update -y

# Install dependencies
dnf install -y cpan gcc-gfortran tk

# Download drivers
wget https://content.mellanox.com/ofed/MLNX_OFED-24.10-2.1.8.0/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz
tar -xf MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz

# Install drivers
~/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64/mlnxofedinstall

# Create autoload kernel module
echo ib_ipoib | tee -a /etc/modules-load.d/ib_ipoib.conf

# Reboot the system
reboot now
