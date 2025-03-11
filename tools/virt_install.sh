#!/bin/bash

# installing virtualization
yes | dnf update -y
yes | dnf install -y qemu-kvm libvirt virt-install virt-manager virt-viewer libguestfs-tools bridge-utils cockpit cockpit-machines pacemaker pcs corosync fence-agents-all resource-agents

