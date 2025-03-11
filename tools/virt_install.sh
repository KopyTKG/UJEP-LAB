#!/bin/bash

# installing virtualization
yes | dnf update
yes | dnf install qemu-kvm libvirt virt-install virt-manager virt-viewer libguestfs-tools bridge-utils cockpit cockpit-machines pacemaker pcs corosync fence-agents-all resource-agents


# start virt
systemctl enable --now libvirtd
systemctl enable --now cockpit.socket
systemctl enable --now pcsd
