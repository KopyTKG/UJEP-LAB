#!/bin/bash

cat << "EOT" > /etc/yum.repos.d/opennebula.repo
[opennebula]
name=OpenNebula Community Edition
baseurl=https://downloads.opennebula.io/repo/6.10/RedHat/$releasever/$basearch
enabled=1
gpgkey=https://downloads.opennebula.io/repo/repo2.key
gpgcheck=1
repo_gpgcheck=1
EOT
yes | yum makecache -y

yes | yum -y install opennebula-node-kvm
systemctl enable libvirtd.service --now

firewall-cmd --add-port=5900-5999/tcp --permanent
firewall-cmd --reload
