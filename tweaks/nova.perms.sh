#!bin/bash

chown nova:nova /usr/lib/python3.9/site-packages/
chmod 775 /usr/lib/python3.9/site-packages/
touch /usr/lib/python3.9/site-packages/instances
systemctl start openstack-nova-compute
