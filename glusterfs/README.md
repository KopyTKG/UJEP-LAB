::include{file=../shared/ansible_base.md}

> [!IMPORTANT]
> Due to RDMA removal in previous versions, GlusterFS is not viable option for out deployment

## Speed

### Write Test

```yaml
TASK [Show Write Bandwidth (MB/s)] ****************************************************************************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Write Speed: 73.208984375 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Write Speed: 73.216796875 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Write Speed: 221.701171875 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Write Speed: 226.25390625 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Write Speed: 223.0048828125 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Write Speed: 222.94140625 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Write Speed: 70.900390625 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Write Speed: 70.9951171875 MB/s"
}
```

### Read Test

```yaml
TASK [Show Read Bandwidth (MB/s)] *****************************************************************************************************
ok: [Rocky-Compute-1] => {
    "msg": "Host Rocky-Compute-1 Read Speed: 522.8984375 MB/s"
}
ok: [Rocky-Compute-2] => {
    "msg": "Host Rocky-Compute-2 Read Speed: 501.6220703125 MB/s"
}
ok: [Rocky-Compute-3] => {
    "msg": "Host Rocky-Compute-3 Read Speed: 509.4208984375 MB/s"
}
ok: [Rocky-Compute-4] => {
    "msg": "Host Rocky-Compute-4 Read Speed: 523.650390625 MB/s"
}
ok: [Rocky-Compute-5] => {
    "msg": "Host Rocky-Compute-5 Read Speed: 518.80859375 MB/s"
}
ok: [Rocky-Compute-6] => {
    "msg": "Host Rocky-Compute-6 Read Speed: 512.78515625 MB/s"
}
ok: [Rocky-Compute-7] => {
    "msg": "Host Rocky-Compute-7 Read Speed: 501.9296875 MB/s"
}
ok: [Rocky-Compute-8] => {
    "msg": "Host Rocky-Compute-8 Read Speed: 518.4150390625 MB/s"
}
```
