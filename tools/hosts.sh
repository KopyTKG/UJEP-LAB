#!/bin/bash

tee /etc/hosts > /dev/null << EOF
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6

10.0.0.1  node1
10.0.0.2  node2
10.0.0.3  node3
10.0.0.4  node4
10.0.0.5  node5
10.0.0.6  node6
10.0.0.7  node7
10.0.0.8  node8

192.168.1.201  Eth-node1
192.168.1.202  Eth-node2
192.168.1.203  Eth-node3
192.168.1.204  Eth-node4
192.168.1.205  Eth-node5
192.168.1.206  Eth-node6
192.168.1.207  Eth-node7
192.168.1.208  Eth-node8

10.0.1.1  controller
EOF

ssh-keygen -t ed25519 -C "root@$(hostname)" -f /root/.ssh/id_ed25519 -N "" -q
