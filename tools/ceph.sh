#!/bin/bash

tee /etc/yum.repos.d/ceph.repo > /dev/null <<EOF
[ceph]
name=Ceph packages for \$basearch
baseurl=https://download.ceph.com/rpm-reef/el9/\$basearch
enabled=1
priority=2
gpgcheck=1
gpgkey=https://download.ceph.com/keys/release.asc

[ceph-noarch]
name=Ceph noarch packages
baseurl=https://download.ceph.com/rpm-reef/el9/noarch
enabled=1
priority=2
gpgcheck=1
gpgkey=https://download.ceph.com/keys/release.asc

[ceph-source]
name=Ceph source packages
baseurl=https://download.ceph.com/rpm-reef/el9/SRPMS
enabled=0
priority=2
gpgcheck=1
gpgkey=https://download.ceph.com/keys/release.asc
EOF

yes | dnf install -y cephadm

firewall-cmd --add-port={8443,3000,9095,9093,9094,9100,9283}/tcp
firewall-cmd --reload



yes | dnf install -y epel-release
yes | dnf config-manager --set-enabled crb
yes | dnf makecache
yes | dnf install -y ceph-common
