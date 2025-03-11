# UJEP-LAB
Lab setup pro 100Gbps clustering

## Usage
1. FW instalaction

```bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/mlnx_fw_update.sh | sudo bash
```

2. Driver installation
```bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/mlnx_ofed_install.sh | sudo bash
```

3. Static ip on IBS1 link 
```bash
# replace the x with correct ip
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/ipoib_static.sh | sudo bash -s 10.0.0.x
```

4. Virtualization and clustering 
```bash
# install all deps + packages for virt 
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/virt_install.sh | sudo bash
```

set password for `hacluster` user on all nodes (**NEEDS TO BE SAME ON ALL NODES**)
```bash
sudo passwd hacluster
```

set proper hostnames on ibs1 network (**ALL NODES**)
```bash
nano /etc/hosts
```

```bash
10.0.0.1 nodeA.lab nodeA
10.0.0.2 nodeB.lab nodeB
10.0.0.3 nodeC.lab nodeC
10.0.0.4 nodeD.lab nodeD
```


authenticate nodes on main node (**RUN ON ONLY ONE NODE**)
```bash
sudo pcs host auth nodeA.lab nodeB.lab nodeC.lab nodeD.lab -u hacluster -p password
```

create cluster on main node (**RUN ON ONLY ONE NODE**)
```bash
sudo pcs cluster setup cluster_name nodeA.lab nodeB.lab nodeC.lab nodeD.lab -u hacluster -p password
```

start cluster
```bash
sudo pcs cluster start --all
sudo pcs cluster enable --all
```
