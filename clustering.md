## Add repo for HA 
```bash
sudo vim /etc/yum.repos.d/CentOS-Stream-HighAvailability.repo
```

```bash
[HighAvailability]
name=CentOS Stream $releasever - HighAvailability
baseurl=https://mirror.stream.centos.org/10-stream/HighAvailability/x86_64/os/
gpgcheck=1
enabled=1
```

## Install HA 
```bash
sudo dnf install -y pacemaker pcs cockpit-ha-cluster
```
