# UJEP-LAB

## Progression

- Setting up ansible -> [ANSIBLE](Ansible/Ansible.md)

1. Testing Ceph -> [CEPH](Ceph.md)
2. Testing Beegfs -> [BEEGFS](BeeGFS.md)
3. Testing NFS_PCS_TargetCLI -> [NFS_PCS_TargetCLI](NFS_PCS_TargetCLI.md)

<table>
<thead>
<tr>
<th>FS Type</th>
<th>Verdict</th>
<th>Notes</th>
</tr>
</thead>
<tbody>
<tr>
<td>Ceph</td>
<td>NOPE</td>
<td>Ceph is stable and usable, but the software overhead is significant, leading to lower performance compared to other file systems.</td>
</tr>
<tr>
<td>BeeGFS</td>
<td>NOPE</td>
<td>BeeGFS offers excellent performance and scalability, making it suitable for high-performance computing environments. However, the fact that OSS / Comunnity version has only Raid0 is no go.</td>
</tr>
<tr>
<td>NFS_PCS_TargetCLI</td>
<td>NOPE</td>
<td>NFS with Pacemaker and TargetCLI is fast and easy to set up, but for the period of testing, Head server decides to nuke them self after every reboot.
</td>
</tr>
<tr>
<td>GlusterFS</td>
<td>NOPE</td>
<td>RDMA support was removed in recent versions, leaving only IPoIB which negates the InfiniBand fabric advantage.</td>
</tr>
<tr>
<td>Lustre</td>
<td>SELECTED</td>
<td>RDMA over InfiniBand achieved via BTF-stripped stock IB modules; FLR for node-level redundancy; cold-boot stabilized via <code>lustre-startup.service</code> (binds the loop10 MGS, discovers MDT by volume label, race-tolerant OST mount). The only candidate that meets performance + redundancy + RDMA + stability simultaneously. See <a href="docs/Lustre.md">docs/Lustre.md</a>.</td>
</tr>
</table>
