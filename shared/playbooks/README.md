# Shared Playbooks

This directory contains common playbooks used across all filesystem implementations (Lustre, GlusterFS, NFS, etc.).

## Available Playbooks

### `cluster_base_setup.yml`

Base cluster configuration shared by all implementations.

**Configures:**
- NTP time synchronization (Chrony with CESNET servers)
- InfiniBand kernel module (ib_ipoib)
- InfiniBand interface (ibs1) with static IPs
- OpenSM subnet manager
- /etc/hosts file with all cluster nodes
- Network routing priority
- Firewall (NTP service)

**Usage:**
```yaml
- import_playbook: ../../shared/playbooks/cluster_base_setup.yml
```

### `prepare_compute_storage.yml`

Storage preparation for compute nodes - discovers, formats, and mounts Samsung SSDs.

**Configures:**
- Discovers Samsung 256GB SSDs (model: MZ7TY256)
- Wipes existing filesystem signatures
- Formats drives with XFS
- Creates mount directories
- Mounts drives with noatime option

**Variables:**
- `target_folder` - Base directory for mounts (default: `/data/storage`)
- `mount_prefix` - Prefix for mount subdirectories (default: `disk`)
- `target_model_string` - SSD model identifier (default: `MZ7TY256`)

**Usage:**
```yaml
- import_playbook: ../../shared/playbooks/prepare_compute_storage.yml
  vars:
    target_folder: "/data/lustre"
    mount_prefix: "ost"
```

**Examples:**
- Lustre: `target_folder: "/data/lustre"`, `mount_prefix: "ost"` → `/data/lustre/ost_0`, `/data/lustre/ost_1`
- GlusterFS: `target_folder: "/data/glusterfs"`, `mount_prefix: "volume"` → `/data/glusterfs/volume_0`, `/data/glusterfs/volume_1`
- NFS: `target_folder: "/data/nfs"`, `mount_prefix: "disk"` → `/data/nfs/disk_0`, `/data/nfs/disk_1`

## Implementation Pattern

Each filesystem implementation should:
1. Import `cluster_base_setup.yml` first
2. Add filesystem-specific firewall rules (if needed)
3. Import `prepare_compute_storage.yml` with appropriate vars
4. Continue with filesystem-specific configuration

**Example (Lustre):**
```yaml
---
# Stage 1: Core Setup
- import_playbook: ../../shared/playbooks/cluster_base_setup.yml

- name: Lustre-specific firewall
  hosts: all
  tasks:
    - name: Open Lustre ports
      ansible.posix.firewalld:
        port: 988/tcp
        permanent: yes
        state: enabled

- import_playbook: ../../shared/playbooks/prepare_compute_storage.yml
  vars:
    target_folder: "/data/lustre"
    mount_prefix: "ost"
```
