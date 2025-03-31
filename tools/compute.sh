#!/bin/bash

curl -fsSl https://stack.thekrew.app/openstack | sudo bash

# installing virtualization
yes | dnf update -y
yes | dnf install -y qemu-kvm qemu-img libvirt libvirt-client libguestfs-tools python3-libvirt



