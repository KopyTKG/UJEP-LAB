#!/bin/bash

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
