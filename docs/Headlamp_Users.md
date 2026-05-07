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
