#!/bin/bash

# Install Cephadm and Ceph common tools on Rocky Linux 10
yes | dnf install -y centos-release-ceph-squid
yes | dnf install -y cephadm

firewall-cmd --add-port={8443,3000,9095,9093,9094,9100,9283}/tcp
firewall-cmd --reload



yes | dnf install -y epel-release
yes | dnf config-manager --set-enabled crb
yes | dnf makecache
yes | dnf install -y ceph-common python3-jinja2
