# UJEP-LAB
Lab setup for 100Gbps IPoIB clustering with Mellanox CX555A

## Usage
1. FW instalaction

```bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/mlnx_fw_update.sh | sudo bash
```

2. Driver installation
```bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/doca_ofed_install.sh | sudo bash
```

3. Static ip on IBS1 link 
```bash
sudo nmtui
```

4. Virtualization and clustering 
```bash
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/virt_install.sh | sudo bash
```

