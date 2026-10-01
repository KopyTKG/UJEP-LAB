# UJEP-LAB — Ansible task runner (tooling via mise, see mise.toml)
#
# Each storage/workload dir (opennebula/, lustre/, ...) is its own Ansible
# project. Pick one with `just project=lustre <recipe>`; default below.

set shell := ["bash", "-cu"]

project := "opennebula"

default:
    @just --list

# Install Ansible + Galaxy collections into the venv
deps:
    mise run setup

# SSH-reach the nodes (subset: `just ping compute` or `just ping Rocky-Head-1`)
ping limit="":
    cd {{project}} && ansible {{ if limit == "" { "all" } else { limit } }} -m ping

# Power on every node via IPMI
up:
    cd {{project}} && ansible-playbook playbooks/common/startup.yml

# Update packages on every node
update limit="":
    cd {{project}} && ansible-playbook playbooks/common/update.yml {{ if limit == "" { "" } else { "--limit " + limit } }}

# Reboot nodes one at a time (subset: `just reboot compute`)
reboot limit="":
    cd {{project}} && ansible-playbook playbooks/common/reboot.yml {{ if limit == "" { "" } else { "--limit " + limit } }}

# Gracefully shut down every node
down limit="":
    cd {{project}} && ansible-playbook playbooks/common/shutdown.yml {{ if limit == "" { "" } else { "--limit " + limit } }}

# Lustre health per node: unit state, client mount, OSTs served (needs vault sudo)
status limit="":
    cd {{project}} && ansible {{ if limit == "" { "cluster" } else { limit } }} -b -m shell -a 'echo "kernel=$(uname -r | cut -c1-22) unit=$(systemctl is-active lustre-startup) mount=$(mountpoint -q /mnt/lustre && echo yes || echo NO) osts=$(lctl dl | grep -c obdfilter) nid=$(lctl list_nids | grep o2ib)"'

# ---- stability tests (tools/stability.py; each run logs to benchmarks/stability/logs/) ----

# Offline self-test of the test tooling (no cluster needed)
stab-selftest:
    python3 tools/test_stability.py

# One-time prep: fio on the computes, /mnt/lustre/stab
stab-prep:
    python3 tools/stability.py prep

# Full health snapshot: kernel, unit, mount, OSTs, NIDs, dmesg errors, 16 OST / 2 MDT
health:
    python3 tools/stability.py health

# Deploy lustre-startup. Default = fixed; `just startup-deploy false` = legacy buggy version
startup-deploy fix="true":
    cd {{project}} && ansible-playbook playbooks/setup_lustre_startup.yml -e startup_fix={{fix}}

# Cold boots: `just coldboot 3`, `just coldboot 1 --head1-delay 240`, `--hard`, `--integrity 40`
coldboot runs="1" *args:
    python3 tools/stability.py coldboot --runs {{runs}} {{args}}

# Reboot loop (heads first, checks Lustre mount): `just rebootloop 5`
rebootloop runs="3" *args:
    python3 tools/stability.py rebootloop --runs {{runs}} {{args}}

# Node loss under write load, mirrored files: `just nodeloss Rocky-Compute-5` / `just nodeloss Rocky-Head-2`
nodeloss victim="Rocky-Compute-5" *args:
    python3 tools/stability.py nodeloss --victim {{victim}} {{args}}

# Soak: mixed fio on all computes, health + error counters each round: `just soak 24`
soak hours="1" *args:
    python3 tools/stability.py soak --hours {{hours}} {{args}}

# Ad-hoc root shell command: `just sh Rocky-Compute-2 'grubby --default-kernel'`
sh limit cmd:
    cd {{project}} && ansible {{limit}} -b -m shell -a '{{cmd}}'

# Re-run lustre-startup on the computes (skips what is already mounted), then show status
lustre-up limit="compute":
    cd {{project}} && ansible {{limit}} -b -m systemd -a "name=lustre-startup state=restarted"
    just project={{project}} status {{limit}}

# List the project's playbooks
list:
    @ls {{project}}/playbooks {{project}}/playbooks/common {{project}}/playbooks/diagnostics 2>/dev/null

# Run a stage by number: `just stage 8` -> playbooks/stage8_*.yml
stage n limit="":
    cd {{project}} && ansible-playbook playbooks/stage{{n}}_*.yml {{ if limit == "" { "" } else { "--limit " + limit } }}

# Run any playbook by path under playbooks/: `just play common/reboot.yml`
play path limit="":
    cd {{project}} && ansible-playbook playbooks/{{path}} {{ if limit == "" { "" } else { "--limit " + limit } }}

# Dry-run any playbook: `just check stage8_mariadb_galera.yml`
check path limit="":
    cd {{project}} && ansible-playbook playbooks/{{path}} {{ if limit == "" { "" } else { "--limit " + limit } }} --check --diff

# Edit the project's vault
vault:
    cd {{project}} && ansible-vault edit group_vars/all/secret.yml
