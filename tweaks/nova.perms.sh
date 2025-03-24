#!bin/bash

mkdir /usr/lib/python3.9/site-packages/instances
chown nova:nova /usr/lib/python3.9/site-packages/
chmod 775 /usr/lib/python3.9/site-packages/
systemctl start openstack-nova-compute
