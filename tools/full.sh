#!/bin/bash

curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/doca_ofed_install.sh | sudo bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/chrony.sh | sudo bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/ceph.sh | sudo bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/hosts.sh | sudo bash

