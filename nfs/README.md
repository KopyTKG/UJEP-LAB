# Ansible setup journey

## Prerequisites

> [!NOTE]
> All commands are run under a user with sudo privileges.

1. Install pip3 if not already installed:
   ```bash
   sudo yum update -y
   sudo yum install pipx -y
   ```
2. Install Ansible using pipx:
   ```bash
   pipx install ansible # This installs ansible-comunity package, which is missing ansible binary
   pipx inject ansible ansible-core --include-apps # This adds the ansible binary
   ```

## Setting up Ansible hosts

All hosts are set up in the [`hosts.ini`](hosts.ini) file. Below is an example configuration:

```ini
[compute]
Rocky-Compute-1 ansible_host=192.168.1.101
Rocky-Compute-2 ansible_host=192.168.1.102
Rocky-Compute-3 ansible_host=192.168.1.103
Rocky-Compute-4 ansible_host=192.168.1.104
Rocky-Compute-5 ansible_host=192.168.1.105
Rocky-Compute-6 ansible_host=192.168.1.106
Rocky-Compute-7 ansible_host=192.168.1.107
Rocky-Compute-8 ansible_host=192.168.1.108

# Variables that apply to all [compute] hosts
[compute:vars]
# Use the non-root user for SSH
ansible_user=user
# Automatically use 'sudo' after login
ansible_become=true
# Point to your private key if it's not default id_rsa
ansible_ssh_private_key_file=~/.ssh/id_ed25519

# We define the IB IPs as variables so we can use them in templates later
ib_ip=10.0.0.{{ ansible_host.split('.')[3] }}
# (Note: The jinja2 logic above is a trick to grab the last octet,
# or you can just hardcode ib_ip line by line above if you prefer)
```

Also config file needs to be created in same folder as the `.ini` file: (file should be named [`ansible.cfg`](ansible.cfg)))

```ini
[defaults]
# Point to your inventory file automatically
inventory = hosts.ini

# Disable the "Are you sure?" prompt
host_key_checking = False

# Use your specific key (since you use ed25519, not the default rsa)
private_key_file = ~/.ssh/id_ed25519
```

## Testing connectivity

To ensure that Ansible can communicate with all defined hosts, run the following command:

```bash
ansible all -m ping
```

## Setup Vault for secrets management

To manage sensitive information securely, we will use Ansible Vault. Follow these steps to set it up:

1. Create a vault
   ```bash
   mkdir -p group_vars/all
   ```
2. Create a vault file to store secrets:
   ```bash
   ansible-vault create group_vars/all/secret.yml
   ```
3. Add your secrets in the vault file in YAML format. For example:
   ```yaml
   ansible_become_pass: your_sudo_password
   hacluster_password: "your_hacluster_password"
   ```
4. When running playbooks that require access to the vault, use the `--ask-vault-pass` option:
   ```bash
   ansible-playbook playbook.yml --ask-vault-pass
   ```

### Add to ansible.cfg (optional)

To avoid typing `--ask-vault-pass` every time, you can add the following line to your `ansible.cfg` file under the `[defaults]` section:

```ini
vault_password_file = ~/.ansible_vault_pass
```

and create the file `~/.ansible_vault_pass` containing your vault password. Make sure to set appropriate permissions on this file to keep it secure:

```bash
echo "MY_VAULT_PASSWORD" > ~/.ansible_vault_pass
chmod 600 ~/.ansible_vault_pass
```

## Rerun tests

After making any changes to the configuration or playbooks, you can rerun your tests using the same Ansible commands as before. For example, to rerun the ping test:

```bash
ansible all -m ping
```

# Next Steps

> [!NOTE]
> All steps are done via Ansible playbooks located in the `playbooks/` directory.

1. `1_setup_core_install.yml` - Installs crony, opensm and enables IB, ntp services.
2. `2_setup_compute_storage.yml` - Configures storage on compute nodes. That includes wiping disks and setting up targetcli LUNs.
3. `3_setup_controller_aggregation.yml` - Configures NFS server with Pacemaker on Head 1.
4. `4_head_1-setup_raid.yml` - Sets up software RAID6 exported LUNs.
5. `5_head_1-setup_ha.yml` - Sets up Pacemaker resources for NFS and TargetCLI.
6. `6_head_2-join_ha.yml` - Joins Head 2 to the Pacemaker cluster.
7. `7_setup_client_mount.yml` - Sets up NFS mounts on compute nodes.

**Common Tools**

- `common/startup.yml` - Startup sequence for all nodes.
- `common/shutdown.yml` - Shutdown sequence for all nodes.
- `benchmark.yml` - Runs FIO benchmark on all compute nodes.
- `heavy_benchmark.yml` - Runs a more intensive FIO benchmark on all compute nodes.

## SPEED TEST

```bash
JEP-LAB/ansible Live  ? ❯ ansible-playbook playbooks/benchmark.yml

PLAY [Distributed Storage Benchmark] **************************************************************************************************

TASK [Gathering Facts] ****************************************************************************************************************
ok: [Rocky-Compute-1]
ok: [Rocky-Compute-2]
ok: [Rocky-Compute-5]
ok: [Rocky-Compute-4]
ok: [Rocky-Compute-3]
ok: [Rocky-Compute-6]
ok: [Rocky-Compute-7]
ok: [Rocky-Compute-8]

TASK [Install FIO] ********************************************************************************************************************
ok: [Rocky-Compute-2]
ok: [Rocky-Compute-3]
ok: [Rocky-Compute-4]
ok: [Rocky-Compute-1]
ok: [Rocky-Compute-5]
ok: [Rocky-Compute-6]
ok: [Rocky-Compute-7]
ok: [Rocky-Compute-8]

TASK [Ensure permission to write] *****************************************************************************************************
ok: [Rocky-Compute-5]
ok: [Rocky-Compute-4]
ok: [Rocky-Compute-1]
ok: [Rocky-Compute-2]
ok: [Rocky-Compute-3]
ok: [Rocky-Compute-6]
ok: [Rocky-Compute-8]
ok: [Rocky-Compute-7]

TASK [Run Write Bandwidth Test (Parallel)] ********************************************************************************************
changed: [Rocky-Compute-5]
changed: [Rocky-Compute-2]
changed: [Rocky-Compute-1]
changed: [Rocky-Compute-4]
changed: [Rocky-Compute-3]
changed: [Rocky-Compute-6]
changed: [Rocky-Compute-8]
changed: [Rocky-Compute-7]

TASK [Parse Write Results] ************************************************************************************************************
ok: [Rocky-Compute-1]
ok: [Rocky-Compute-2]
ok: [Rocky-Compute-3]
ok: [Rocky-Compute-4]
ok: [Rocky-Compute-5]
ok: [Rocky-Compute-6]
ok: [Rocky-Compute-7]
ok: [Rocky-Compute-8]

TASK [Show Write Bandwidth (MB/s)] ****************************************************************************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Write Speed: 1233.2705078125 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Write Speed: 1241.3056640625 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Write Speed: 1227.44921875 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Write Speed: 1230.6767578125 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Write Speed: 1242.2470703125 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Write Speed: 1753.236328125 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Write Speed: 1537.9697265625 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Write Speed: 1550.7802734375 MB/s"
}

TASK [Run Read Bandwidth Test (Parallel)] *********************************************************************************************
changed: [Rocky-Compute-1]
changed: [Rocky-Compute-5]
changed: [Rocky-Compute-3]
changed: [Rocky-Compute-2]
changed: [Rocky-Compute-4]
changed: [Rocky-Compute-6]
changed: [Rocky-Compute-8]
changed: [Rocky-Compute-7]

TASK [Parse Read Results] *************************************************************************************************************
ok: [Rocky-Compute-1]
ok: [Rocky-Compute-2]
ok: [Rocky-Compute-3]
ok: [Rocky-Compute-4]
ok: [Rocky-Compute-5]
ok: [Rocky-Compute-6]
ok: [Rocky-Compute-7]
ok: [Rocky-Compute-8]

TASK [Show Read Bandwidth (MB/s)] *****************************************************************************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Read Speed: 2205.1142578125 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Read Speed: 2031.2421875 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Read Speed: 2060.8798828125 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Read Speed: 1784.7490234375 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Read Speed: 2080.5078125 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Read Speed: 3263.0947265625 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Read Speed: 2552.421875 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Read Speed: 2660.603515625 MB/s"
}

TASK [Cleanup Test Files] *************************************************************************************************************
changed: [Rocky-Compute-1]
changed: [Rocky-Compute-2]
changed: [Rocky-Compute-3]
changed: [Rocky-Compute-4]
changed: [Rocky-Compute-5]
changed: [Rocky-Compute-6]
changed: [Rocky-Compute-7]
changed: [Rocky-Compute-8]

PLAY RECAP ****************************************************************************************************************************
Rocky-Compute-1            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-2            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-3            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-4            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-5            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-6            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-7            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
Rocky-Compute-8            : ok=10   changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


UJEP-LAB/ansible Live  ? ❯
```

Agregate results:

- Write Speeds (MB/s):
  - Rocky-Compute-1: 1233.27
  - Rocky-Compute-2: 1241.31
  - Rocky-Compute-3: 1227.45
  - Rocky-Compute-4: 1230.68
  - Rocky-Compute-5: 1242.25
  - Rocky-Compute-6: 1753.24
  - Rocky-Compute-7: 1537.97
  - Rocky-Compute-8: 1550.78
- Read Speeds (MB/s):
  - Rocky-Compute-1: 2205.11
  - Rocky-Compute-2: 2031.24
  - Rocky-Compute-3: 2060.88
  - Rocky-Compute-4: 1784.75
  - Rocky-Compute-5: 2080.51
  - Rocky-Compute-6: 3263.09
  - Rocky-Compute-7: 2552.42
  - Rocky-Compute-8: 2660.60

- Total Write Speed across all nodes: 11,835.69 MB/s (94.68 Gbit/s)
- Total Read Speed across all nodes: 19,678.58 MB/s (157.43 Gbit/s)
