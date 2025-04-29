#!/bin/bash

galera_new_cluster
systemctl set-environment _WSREP_NEW_CLUSTER='--wsrep-new-cluster'
systemctl start mariadb
