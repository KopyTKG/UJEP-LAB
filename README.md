# UJEP-LAB
Lab setup pro 100Gbps clustering

## Usage
1. FW instalaction

```bash
sudo su &&
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/mlnx_fw_update.sh%20 | bash
```

2. Driver installation
```bash
sudo su &&
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/mlnx_ofed_install.sh | bash
```

3. Static ip on IBS1 link 
```bash
sudo su && 
# replace the x with correct ip
curl -fsSl https://raw.githubusercontent.com/KopyTKG/UJEP-LAB/refs/heads/Live/tools/ipoib_static.sh | sudo bash -s 10.0.0.x
```

