#!/bin/bash

# update
dnf update -y

# download deps
dnf install -y cpan gcc-gfortran tk &&

# download drivers
wget https://content.mellanox.com/ofed/MLNX_OFED-24.10-2.1.8.0/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz &&
tar -xf MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz &&

# Install drivers 
~/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64/mlnxofedinstall

# Create autoload kernel module
echo ib_ipoib | tee -a /etc/modules-load.d/ib_ipoib.conf

reboot now

