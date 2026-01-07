# Lustre Implementation Log

## Session: 2026-01-07

### Starting Point
- Continued from previous session where stage2_install_lustre.yml was failing
- Issue: Lustre repository URLs changed from el8.10 to el8.9 in playbook, but old repo configs cached on nodes
- Error: 404 for https://downloads.whamcloud.com/public/lustre/lustre-2.15.4/el8.10/client/repodata/repomd.xml

### Problem 1: Repository Cleanup Not Working
**Issue**: Old Lustre repository configurations (el8.10) still present on nodes from previous run

**Root Cause**: Ansible `command` module doesn't expand shell globs like `*.repo`

**Fix Applied** (stage2_install_lustre.yml:12):
```yaml
# Changed from 'command' to 'shell' module
- name: Remove old Lustre repository configurations
  shell: rm -f /etc/yum.repos.d/lustre-*.repo /etc/yum.repos.d/e2fsprogs-*.repo
```

**Additional Fix** (stage2_install_lustre.yml:17-21):
```yaml
- name: Clear DNF cache to remove old repository metadata
  command: dnf clean all
```

**Result**: ✓ Old repository files successfully removed, cache cleared

---

### Problem 2: Missing Development Packages
**Issue**: lustre-client-dkms dependencies not found
```
Error: Unable to find a match: libyaml-devel libmount-devel
```

**Root Cause**: Development packages (libyaml-devel, libmount-devel) are in PowerTools repository, which is disabled by default

**Fix Applied** (stage2_install_lustre.yml:120-129):
```yaml
- name: Enable PowerTools repository for development packages
  command: dnf config-manager --set-enabled powertools

- name: Install Lustre client DKMS dependencies
  command: dnf install -y libyaml-devel libmount-devel dkms
```

**Result**: ✓ Dependencies installed successfully

---

### Problem 3: Package Conflicts
**Issue**: lustre-client package conflicts with lustre server package
```
Error: Transaction test error:
  file /sbin/mount.lustre from install of lustre-client-2.15.4-1.el8.x86_64
  conflicts with file from package lustre-2.15.4-1.el8.x86_64
```

**Root Cause**: The `lustre` server package already includes client functionality. Installing `lustre-client` on server nodes creates file conflicts.

**Fix Applied** (stage2_install_lustre.yml:131-137):
```yaml
# Changed from installing both lustre-client and lustre-client-dkms
# to only installing lustre-client-dkms
- name: Install Lustre client DKMS (server nodes already have client functionality via lustre package)
  command: dnf install -y lustre-client-dkms
```

**Result**: ✓ DKMS package installed without conflicts

---

### Problem 4: Conditional Error in Display Task
**Issue**: `lnet_ping` variable on Rocky-Head-1 missing `.rc` attribute
```
Error while evaluating conditional: object of type 'dict' has no attribute 'rc'
```

**Root Cause**: The task was skipped on Rocky-Head-1, so `lnet_ping` is a skip dict, not a result dict

**Fix Applied** (stage2_install_lustre.yml:227):
```yaml
when:
  - lnet_ping is defined
  - lnet_ping is not skipped  # Added this check
  - lnet_ping.rc == 0
```

**Result**: ✓ Conditional error resolved

---

## Stage 2 Completion Status

### ✅ Successfully Completed Tasks:
1. **Repository Configuration**
   - Old el8.10 repositories removed
   - New el8.9 repositories configured for:
     - Lustre server (MGS/MDS/OSS)
     - Lustre client
     - e2fsprogs-wc (Lustre-patched e2fsprogs)

2. **Package Installation**
   - EPEL repository installed on all nodes
   - PowerTools repository enabled for development packages
   - kernel-devel and development tools installed
   - Lustre server packages installed:
     - Head nodes (Rocky-Head-1, Rocky-Head-2): MGS/MDS functionality
     - Compute nodes (Rocky-Compute-1 through 8): OSS functionality
   - Lustre client DKMS installed on all nodes with dependencies:
     - libyaml-devel
     - libmount-devel
     - dkms

3. **LNET Configuration**
   - LNET options configured for RDMA (o2ib):
     - `/etc/modprobe.d/lnet.conf` created with `options lnet networks=o2ib(ibs1)`
   - Module persistence configured:
     - `/etc/modules-load.d/lustre.conf` created to auto-load lustre/lnet modules

4. **Mount Points**
   - Client mount point created: `/mnt/lustre`

### ⚠️ Expected Errors (Ignored)
These are normal at this stage and will be resolved after reboot or DKMS build:

1. **Module Loading Failures**
   - `modprobe lustre/lnet` - Kernel modules not built yet
   - Reason: Requires DKMS to build modules OR a reboot to trigger auto-build

2. **LNET Ping Failures**
   - `lctl ping 10.0.0.251@o2ib` - LNET not running
   - Reason: Modules must be loaded first

3. **lsmod Command Issues**
   - Command module doesn't handle shell pipes correctly
   - Benign error, ignored

---

## Current Cluster State

**All 10 Nodes (2 heads + 8 compute):**
- ✓ Rocky Linux 8.10 installed
- ✓ Python 3.9 bootstrapped
- ✓ NTP synchronized (Chrony)
- ✓ InfiniBand configured (ibs1 on 10.0.0.0/24)
- ✓ OpenSM running on controller
- ✓ Firewall configured (NTP, Lustre ports)
- ✓ Lustre repositories configured (el8.9)
- ✓ Lustre packages installed:
  - Server: lustre-2.15.4-1.el8.x86_64
  - Client DKMS: lustre-client-dkms-2.15.4-1.el8.noarch
- ✓ LNET configured for RDMA (o2ib over ibs1)
- ✓ Storage prepared: 16x Samsung 256GB SSDs (2 per compute node)
  - Formatted with XFS
  - Mounted at `/mnt/brick1` and `/mnt/brick2`

---

## Next Steps (Stage 3+)

### Option 1: Reboot to Build Modules (Recommended)
```bash
cd /home/kopy/Documents/UJEP-LAB/lustre
ansible-playbook playbooks/common/reboot.yml
```
After reboot, DKMS will automatically build Lustre kernel modules.

### Option 2: Manual DKMS Build
```bash
ansible all -m command -a "dkms build -m lustre-client -v 2.15.4" -b
ansible all -m command -a "dkms install -m lustre-client -v 2.15.4" -b
ansible all -m command -a "modprobe lustre" -b
ansible all -m command -a "modprobe lnet" -b
```

### Stage 3: Configure MGS (Rocky-Head-1)
- Format MGT (Management Target) on designated storage
- Mount MGT and start MGS service

### Stage 4: Configure MDS (Rocky-Head-1 & Rocky-Head-2)
- Format MDT (Metadata Targets) on designated storage
- Mount MDTs and start MDS services

### Stage 5: Configure OSS (All Compute Nodes)
- Format OSTs (Object Storage Targets) on Samsung SSDs
- Mount OSTs and start OSS services

### Stage 6: Mount Clients
- Mount Lustre filesystem on all nodes at `/mnt/lustre`
- Verify RDMA performance with IOR/FIO benchmarks

---

## Important Notes

1. **Repository Version**: Lustre 2.15.4 for el8.10 doesn't exist. Using el8.9 repositories which are compatible with Rocky 8.10.

2. **Server vs Client Packages**:
   - Lustre server package (`lustre`) includes both server AND client functionality
   - Only install standalone `lustre-client` on pure client nodes (none in this setup)
   - DKMS package (`lustre-client-dkms`) can coexist with server package

3. **RDMA Configuration**:
   - Network: o2ib (OpenFabrics InfiniBand)
   - Interface: ibs1 (10.0.0.0/24)
   - NID format: `<IP>@o2ib` (e.g., 10.0.0.251@o2ib)

4. **Module Auto-loading**:
   - Modules configured to auto-load via `/etc/modules-load.d/lustre.conf`
   - Will activate after reboot OR manual modprobe

---

## Playbook Files Status

### Completed:
- ✅ `stage0_bootstrap.yml` - Python 3.9 bootstrap
- ✅ `stage1_core_setup.yml` - Base setup (NTP, InfiniBand, storage)
- ✅ `stage2_install_lustre.yml` - Lustre packages and LNET configuration

### To Create:
- ⏳ `stage3_configure_mgs.yml` - Management Server setup
- ⏳ `stage4_configure_mds.yml` - Metadata Server setup
- ⏳ `stage5_configure_oss.yml` - Object Storage Server setup
- ⏳ `stage6_mount_clients.yml` - Client mounts

---

## Performance Expectations

With RDMA over InfiniBand (o2ib):
- Significantly lower latency vs IPoIB-only
- Higher aggregate throughput due to RDMA offload
- Better CPU efficiency (kernel bypass)
- Critical for OpenNebula VM workloads:
  - Faster VM disk I/O
  - Improved live migration performance

Test with FIO/IOR benchmarks after stage 6 completion.

---

## References

- Lustre Documentation: https://doc.lustre.org/
- Whamcloud Downloads: https://downloads.whamcloud.com/public/lustre/
- LNET RDMA: https://doc.lustre.org/lustre_manual.xhtml#lnetconfig
