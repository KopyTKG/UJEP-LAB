#!/bin/bash

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
