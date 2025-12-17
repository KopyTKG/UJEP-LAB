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
