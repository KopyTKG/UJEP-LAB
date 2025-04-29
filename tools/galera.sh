#!/bin/bash

# Update the system
yes | dnf update -y
if [ $? -ne 0 ]; then
  echo "Failed to update the system."
  exit 1
fi

yes | dnf install -y mariadb-server galera
if [ $? -ne 0 ]; then
  echo "Failed to install mariadb-server or galera."
  exit 1
fi

systemctl enable --now mariadb.service
if [ $? -ne 0 ]; then
	echo "Failed to activate mariadb."
	exit 1
fi



firewall-cmd --permanent --add-port=3306/tcp
firewall-cmd --permanent --add-port=4567/tcp
firewall-cmd --permanent --add-port=4568/tcp
firewall-cmd --permanent --add-port=4444/tcp
firewall-cmd --reload
