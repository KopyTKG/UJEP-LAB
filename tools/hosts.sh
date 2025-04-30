#!/bin/bash/

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

10.0.1.1  controller1
EOF
