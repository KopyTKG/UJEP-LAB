#!/bin/bash

yes | dnf install mariadb mariadb-server python3-PyMySQL -y
yes | dnf install rabbitmq-server -y

systemctl enable mariadb.service rabbitmq-server.service --now

echo "Please create or edit /etc/my.cnf.d/openstack.cnf and reload database service"
echo "https://docs.openstack.org/install-guide/environment-sql-database-rdo.html"

echo "Please follow Rabbitmq confing"
echo "https://docs.openstack.org/install-guide/environment-messaging-rdo.html"
