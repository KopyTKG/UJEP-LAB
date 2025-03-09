#!/bin/bash

# download deps
dnf install cpan gcc-gfortran tk &&
# download drivers
wget https://content.mellanox.com/ofed/MLNX_OFED-24.10-2.1.8.0/MLNX_OFED_LINUX-24.10-2.1.8.0-rhel9.5-x86_64.tgz &&
tar -xf MLNX &&
cd MLNX 
./mlnxofedinstall

echo "Done please reboot system to load drivers"
