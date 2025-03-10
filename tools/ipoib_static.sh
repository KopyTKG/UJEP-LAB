#!/bin/bash

# Prompt the user for the IP address
read -p "Enter IP: " IP

# Create the configuration file with the defined content
sudo tee /etc/sysconfig/network-scripts/ifcfg-ibs1 > /dev/null <<EOF
TYPE=InfiniBand
BOOTPROTO=none
NAME=ibs1
DEVICE=ibs1
ONBOOT=yes
IPADDR=$IP
NETMASK=255.255.255.0
GATEWAY=10.0.0.254
EOF

# Inform the user that the configuration file has been created
echo "Configuration file for ibs1 has been created successfully."
