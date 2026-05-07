# Headlamp users & RBAC

Headlamp has no user database of its own — authentication is delegated to Kubernetes. To create a "user" you provision a Kubernetes **ServiceAccount**, bind it to one or more roles via **RBAC**, and issue it a bearer token. The user pastes that token into Headlamp's login screen.

This document defines three reference role profiles for the lab, plus the kubectl commands to provision them. Tokens are not committed — issue them per-user with `kubectl create token` and distribute via secure channel.

## Role profiles

| Profile | Cluster-wide rights | Namespace rights | Typical use |
|---|---|---|---|
| **Admin** | `cluster-admin` (full) | n/a | Lab operator. Full read/write across all namespaces, can mutate RBAC, can install operators, can wipe state. One per lab. |
| **Student** | `view` (read-only) | `admin` in their own `student-<name>` ns | Lab participant. Can see everything in the cluster (useful for learning) but can only *create/modify* resources in their personal sandbox namespace. |
| **Guest** | `view` (read-only) | none | Demos, visitors. Read-only across the entire cluster. Cannot create or change anything. |

`view` and `admin` here refer to the upstream `ClusterRole`s shipped with Kubernetes (`kubectl get clusterrole view admin cluster-admin`). They cover sensible defaults for each scope and don't need to be hand-written.

## Provisioning

All commands below are run from any node with `kubectl` configured (typically `Rocky-Head-1` as root, where `/etc/kubernetes/admin.conf` is the kubeconfig).

Each profile lives in the `headlamp` namespace by default, but ServiceAccounts can be in any namespace — the RBAC bindings are what determine what they can do.

### Admin

The cluster already has one `admin-user` ServiceAccount in the `headlamp` namespace bound to `cluster-admin`. To re-issue a long-lived token for the existing admin:

```bash
kubectl create token admin-user -n headlamp --duration=8760h
```

To create an additional named admin (e.g. `kopy`):

```bash
NAME=kopy

kubectl create serviceaccount "$NAME" -n headlamp

kubectl create clusterrolebinding "${NAME}-cluster-admin" \
  --clusterrole=cluster-admin \
  --serviceaccount="headlamp:$NAME"

kubectl create token "$NAME" -n headlamp --duration=8760h
```

The last command prints the JWT to stdout — paste it into Headlamp.

### Student

Each student gets a personal namespace `student-<name>`, full admin in that namespace, and read-only access cluster-wide. Substitute the student's name for `alice`:

```bash
NAME=alice
NS="student-${NAME}"

# 1. Personal namespace
kubectl create namespace "$NS"

# 2. ServiceAccount lives in their own namespace
kubectl create serviceaccount "$NAME" -n "$NS"

# 3. Full admin within their own namespace (the upstream 'admin' ClusterRole,
#    bound at namespace scope via RoleBinding — not ClusterRoleBinding).
kubectl create rolebinding "${NAME}-ns-admin" \
  --clusterrole=admin \
  --serviceaccount="${NS}:${NAME}" \
  -n "$NS"

# 4. Cluster-wide read-only (so they can see other namespaces' pods etc.).
#    Skip this binding if you want true isolation — see the Guest section
#    for what 'view' covers exactly.
kubectl create clusterrolebinding "${NAME}-cluster-view" \
  --clusterrole=view \
  --serviceaccount="${NS}:${NAME}"

# 5. Issue token (valid 1 year)
kubectl create token "$NAME" -n "$NS" --duration=8760h
```

To create multiple students at once, wrap the above in a loop:

```bash
for NAME in alice bob carol; do
  NS="student-${NAME}"
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create serviceaccount "$NAME" -n "$NS" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create rolebinding "${NAME}-ns-admin" \
    --clusterrole=admin --serviceaccount="${NS}:${NAME}" -n "$NS" \
    --dry-run=client -o yaml | kubectl apply -f -
  kubectl create clusterrolebinding "${NAME}-cluster-view" \
    --clusterrole=view --serviceaccount="${NS}:${NAME}" \
    --dry-run=client -o yaml | kubectl apply -f -
  echo "=== $NAME ==="
  kubectl create token "$NAME" -n "$NS" --duration=8760h
done
```

(The `--dry-run=client -o yaml | kubectl apply -f -` pattern makes the script idempotent — safe to re-run.)

### Guest

Read-only across the entire cluster. Useful for demos and visiting reviewers.

```bash
NAME=guest

kubectl create serviceaccount "$NAME" -n headlamp
kubectl create clusterrolebinding "${NAME}-cluster-view" \
  --clusterrole=view \
  --serviceaccount="headlamp:$NAME"
kubectl create token "$NAME" -n headlamp --duration=720h   # 30 days for guests
```

Shorter-lived tokens for guests are a good default — they're not expected to be permanent.

## Logging in to Headlamp

1. Browse to `https://dashboard.lab.local/`
2. The login screen offers a **Token** field
3. Paste the JWT from `kubectl create token`
4. Headlamp negotiates with the kube-apiserver; the user lands in the dashboard scoped to whatever the token's RBAC allows

If they see "Forbidden" errors clicking around, that's not a bug — it's the RBAC working as designed. The student / guest profiles will get `403` on any namespace they don't have rights to mutate.

## Listing existing users

```bash
# All ServiceAccounts that look like Headlamp users
kubectl get sa -A | grep -E 'admin-user|^student-|guest'

# What permissions does a given SA have?
kubectl auth can-i --list --as=system:serviceaccount:student-alice:alice
```

The second command is gold for verifying RBAC is what you intended.

## Revoking access

```bash
# Soft revocation — keep the SA but invalidate all its tokens
kubectl delete --all secrets -n <namespace> --field-selector type=kubernetes.io/service-account-token
# Note: kubectl create token --duration is short-lived bearer-token, no associated Secret.
# To invalidate immediately, delete the SA — it ends all in-flight tokens for that SA.

# Hard revocation — delete the SA + all RBAC bindings
NAME=alice
NS="student-${NAME}"
kubectl delete clusterrolebinding "${NAME}-cluster-view"
kubectl delete rolebinding "${NAME}-ns-admin" -n "$NS"
kubectl delete serviceaccount "$NAME" -n "$NS"
# Optionally delete the namespace and everything in it:
kubectl delete namespace "$NS"
```

## Reference

- `kubectl get clusterrole cluster-admin -o yaml` — verbs allowed by cluster-admin
- `kubectl get clusterrole admin -o yaml` — verbs allowed by namespace admin
- `kubectl get clusterrole view -o yaml` — read-only verbs only
- Headlamp docs on auth: <https://headlamp.dev/docs/latest/installation/in-cluster/>
- Kubernetes RBAC docs: <https://kubernetes.io/docs/reference/access-authn-authz/rbac/>

---

## Provisioned accounts

> [!CAUTION]
> The tokens below are bearer credentials. Anyone holding the string IS that user with that user's permissions. Do **not** share them outside the lab. Rotate (`kubectl create token --duration=...`) if exposure is suspected — the previous token remains valid for the duration it was issued for, but new tokens carry no relation to old ones, so any token-leak surface should be re-issued and the namespace-bound SA can be deleted to invalidate everything.

Issued 2026-05-07 on cluster `https://192.168.1.250:8443`.

| Role | ServiceAccount | Namespace | Scope | Expires |
|---|---|---|---|---|
| Admin | `admin-user` | `headlamp` | cluster-admin | 2027-05-07 |
| Student | `student` | `student-default` | ns admin in `student-default` + cluster `view` | 2027-05-07 |
| Guest | `guest` | `headlamp` | cluster `view` | 2026-06-06 |

### Admin token

```
eyJhbGciOiJSUzI1NiIsImtpZCI6IjEtYlJJUTRoV1I2R3g1LW0wTHZRQXM0aXVaVU5mRVRpRFJuTm1hbkoyVGsifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjoxODA5NjgyMjczLCJpYXQiOjE3NzgxNDYyNzMsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiZTI1YmQ4YzUtYWRkOS00MTZiLWE2NzYtMjFlMTY5Y2RmNjM5Iiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJoZWFkbGFtcCIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJhZG1pbi11c2VyIiwidWlkIjoiNDJmMDQ3MzgtZDFiOC00MjE2LTg2MTktMzY5MzAwOTQyM2I5In19LCJuYmYiOjE3NzgxNDYyNzMsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpoZWFkbGFtcDphZG1pbi11c2VyIn0.HB5fzS1PQI9xhnt7NTCFYw3U07emdU0PB4vHhr8ANWs_RxjOwHjW6beGfnopf2v4fKqmp35HvEdLFTHdzdXjn8WolQsuj3_izVCZgC6wGATlpmj0WtFAjAlcV9WyfAGYy-_NEzwP4lMryOagd1YXOLXMZTo4NAJB9VLG3dcjHfOv4h2osDJlHY9XrCqDBmXz17n6vFPLC4g2dHnRswJ3Bibk9x3S7tDKU0C0jGRFrtXY4JkMWxCXnxCTOs2mFzGCiB-7ZKBUCf-aocTbRe48unTVosmoA-EXVKNiHfkHA4HfHw_yq2dIcGxQ9K0Aj1x5ffpFHvyL916VipLqjpKQCg
```

### Student token

```
eyJhbGciOiJSUzI1NiIsImtpZCI6IjEtYlJJUTRoV1I2R3g1LW0wTHZRQXM0aXVaVU5mRVRpRFJuTm1hbkoyVGsifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjoxODA5NjgyMjczLCJpYXQiOjE3NzgxNDYyNzMsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiMTlkZjQxYjUtMGI4MC00MzI3LTgyMDktZThjMDc3ZmRmN2E3Iiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJzdHVkZW50LWRlZmF1bHQiLCJzZXJ2aWNlYWNjb3VudCI6eyJuYW1lIjoic3R1ZGVudCIsInVpZCI6IjMwZjEyNzRlLTM1MjYtNDkyMy1hYjkwLWVmN2M5NDZhNWI1MSJ9fSwibmJmIjoxNzc4MTQ2MjczLCJzdWIiOiJzeXN0ZW06c2VydmljZWFjY291bnQ6c3R1ZGVudC1kZWZhdWx0OnN0dWRlbnQifQ.NlxtN9OMHCHQR-efX-z4YH_3UirTNb4JMTapb_WnyMlenYgN5XOU6rzTySaotOff4I1PBCudB9z1sFb6e9U2QMF07r1y3JBCqdhziW60ye89mHO1cmlrKtJNnbVe7eCZCRb9L1skg17GzpeOEX4ANu4HZJjbpj6MRY8JkLEWfAX-je6LOz5jh7FI7M5xN3MBuHy7wZ0aOWK7xcZcMcOb4wEdNdUYBlQiDOjJY2_3SFtJ_HZs6kVwpAnNHvOO9h0gEiXsvvAueNLnngwdNE5pQE9sl4G2_NnBFmRgWku9SRvobPdCNMaoPWIGkp1I2L23PL9GD9M1sax6lxfyM4H2JQ
```

### Guest token

```
eyJhbGciOiJSUzI1NiIsImtpZCI6IjEtYlJJUTRoV1I2R3g1LW0wTHZRQXM0aXVaVU5mRVRpRFJuTm1hbkoyVGsifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjoxNzgwNzM4MjczLCJpYXQiOjE3NzgxNDYyNzMsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiMDBhYzc4ZGQtYTNmNy00YmJjLWIyOGUtOWRjODNiNjFmYTQ4Iiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJoZWFkbGFtcCIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJndWVzdCIsInVpZCI6IjllNTEwMzJkLTViODItNDk3NC05ZmQxLTQ4OGUwNjcxODZkNyJ9fSwibmJmIjoxNzc4MTQ2MjczLCJzdWIiOiJzeXN0ZW06c2VydmljZWFjY291bnQ6aGVhZGxhbXA6Z3Vlc3QifQ.jH8hhttgjmexZg0ETWSOVnWijunGJMq57IVM1saG-96KIvRmqaLKgwIEwl47Hh2-r5kssvHvNVf6-nvM0_3utwA-EYkif7Zu2Gpq4pjkseZHENmPld_t5akub774cIrr6menSTiungfPKGokDRu49atrAn1pamkYoERTqMlXva-q4N4t4JHocMGJcFc5cnPx8x39EW-Pk_itKesqO-VZp6m4Hd6hUwXwCn95G_eXXKit_E5phTj5r7-jGtyom97L_jwASnjZqlXK2Fxbm9U76wCLFuSXHt04WQ3oVhwv22lr0IqFpQt2EdAGpmmdOUKPR0ylVN9bGoQ9rIJU9XZqbA
```
