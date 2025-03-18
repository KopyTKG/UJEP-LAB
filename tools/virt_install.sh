#!/bin/bash

# installing virtualization
yes | dnf update -y
yes | dnf install -y qemu-kvm qemu-img libvirt libvirt-client libguestfs-tools python3-libvirt


# prep for openstack
yes | dnf install -y chrony

systemctl enable chronyd.service --now

tee /etc/chrony.conf > /dev/null <<EOF
server tik.cesnet.cz iburst
server tak.cesnet.cz iburst

sourcedir /run/chrony-dhcp
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
keyfile /etc/chrony.keys
ntsdumpdir /var/lib/chrony
leapsectz right/UTC
logdir /var/log/chrony
EOF

firewall-cmd --permanent --add-service=ntp
firewall-cmd --reload

systemctl restart chronyd.service

yes | dnf install dnf-plugins-core -y
yes | dnf config-manager --set-enabled crb -y
yes | dnf install centos-release-openstack-dalmatian -y
yes | dnf upgrade -y
yes | dnf install python3-openstackclient -y
yes | dnf install openstack-selinux -y

yes | dnf install mariadb mariadb-server python3-PyMySQL -y
yes | dnf install rabbitmq-server -y

systemctl enable mariadb.service rabbitmq-server.service --now

echo "Please create or edit /etc/my.cnf.d/openstack.cnf and reload database service"
echo "https://docs.openstack.org/install-guide/environment-sql-database-rdo.html"

echo "Please follow Rabbitmq confing"
echo "https://docs.openstack.org/install-guide/environment-messaging-rdo.html"
