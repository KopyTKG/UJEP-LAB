#!/bin/bash

# Update the system
yes | dnf update -y
if [ $? -ne 0 ]; then
  echo "Failed to update the system."
  exit 1
fi

yes | dnf install -y mariadb-server
if [ $? -ne 0 ]; then
  echo "Failed to install mariadb-server."
  exit 1
fi

systemctl enable --now mariadb.service
if [ $? -ne 0 ]; then
	echo "Failed to activate mariadb."
	exit 1
fi


firewall-cmd --permanent --add-port=3306/tcp
firewall-cmd --reload
