# Kubernetes Deployment Guide

Deploy Agentic Brain to Kubernetes using Kustomize or Helm.

## Prerequisites

- Kubernetes cluster (1.25+)
- `kubectl` configured
- `helm` v3.x (for Helm deployment)
- Neo4j and Redis deployed (or external services)

## Quick Start

### Using Kustomize

```bash
# Development (1 replica, debug mode)
kubectl apply -k k8s/overlays/dev

# Production (3+ replicas, autoscaling)
kubectl apply -k k8s/overlays/prod
```

### Using Helm

```bash
# Install
helm install agentic-brain ./helm/agentic-brain \
  --namespace agentic-brain \
  --create-namespace \
  --set neo4j.password=your_secure_password \
  --set auth.jwtSecret=$(openssl rand -hex 32)

# Upgrade
helm upgrade agentic-brain ./helm/agentic-brain \
  --namespace agentic-brain \
  -f values-prod.yaml
```

---

## Kustomize Deployment

### Directory Structure

```
k8s/
├── base/                    # Base manifests
│   ├── deployment.yaml      # 3 replicas, resource limits
│   ├── service.yaml         # ClusterIP on 8000
│   ├── configmap.yaml       # Non-sensitive config
│   ├── secret.yaml          # Template for secrets
│   ├── ingress.yaml         # Nginx ingress + TLS
│   ├── hpa.yaml             # Autoscaler 3-10 replicas
│   └── kustomization.yaml
├── overlays/
│   ├── dev/                 # Development overrides
│   │   └── kustomization.yaml
│   └── prod/                # Production overrides
│       └── kustomization.yaml
```

### Deploy Development Environment

```bash
# Create namespace
kubectl create namespace agentic-brain-dev

# Create secrets first
kubectl create secret generic dev-agentic-brain-secrets \
  --namespace agentic-brain-dev \
  --from-literal=NEO4J_PASSWORD=devpassword \
  --from-literal=JWT_SECRET=devsecret123456789012345678901234 \
  --from-literal=REDIS_URL=redis://redis:6379

# Deploy
kubectl apply -k k8s/overlays/dev

# Verify
kubectl get pods -n agentic-brain-dev
kubectl logs -n agentic-brain-dev -l app=agentic-brain -f
```

### Deploy Production Environment

```bash
# Create namespace
kubectl create namespace agentic-brain-prod

# Create secrets (use real values!)
kubectl create secret generic prod-agentic-brain-secrets \
  --namespace agentic-brain-prod \
  --from-literal=NEO4J_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=JWT_SECRET=$(openssl rand -hex 32) \
  --from-literal=REDIS_URL=redis://redis:6379 \
  --from-literal=API_KEYS=key1,key2,key3

# Deploy
kubectl apply -k k8s/overlays/prod

# Verify
kubectl get pods -n agentic-brain-prod
kubectl get hpa -n agentic-brain-prod
```

### Configuration

The base configmap includes:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `AUTH_ENABLED` | `true` | Enable authentication |
| `SESSION_BACKEND` | `redis` | Session storage |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |

Override in overlays:

```yaml
# k8s/overlays/dev/kustomization.yaml
configMapGenerator:
  - name: agentic-brain-config
    behavior: merge
    literals:
      - LOG_LEVEL=DEBUG
      - AUTH_ENABLED=false
```

---

## Helm Deployment

### Install Chart

```bash
# Minimal installation
helm install agentic-brain ./helm/agentic-brain \
  --set neo4j.password=changeme \
  --set auth.jwtSecret=changeme

# Full production installation
helm install agentic-brain ./helm/agentic-brain \
  --namespace agentic-brain \
  --create-namespace \
  --set replicaCount=3 \
  --set neo4j.password=$(openssl rand -hex 16) \
  --set neo4j.uri=bolt://neo4j.database:7687 \
  --set redis.url=redis://redis.cache:6379 \
  --set auth.enabled=true \
  --set auth.jwtSecret=$(openssl rand -hex 32) \
  --set auth.apiKeys[0]=api-key-1 \
  --set auth.apiKeys[1]=api-key-2 \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=api.example.com \
  --set ingress.tls[0].hosts[0]=api.example.com
```

### Custom Values File

Create `values-prod.yaml`:

```yaml
replicaCount: 5

resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1000m"

neo4j:
  uri: "bolt://neo4j-cluster:7687"
  password: ""  # Set via --set

auth:
  enabled: true
  jwtSecret: ""  # Set via --set

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.production.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: prod-tls-cert
      hosts:
        - api.production.example.com

autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 20
```

Deploy:

```bash
helm install agentic-brain ./helm/agentic-brain \
  -f values-prod.yaml \
  --set neo4j.password=$NEO4J_PASSWORD \
  --set auth.jwtSecret=$JWT_SECRET
```

### Upgrade

```bash
# Upgrade with new image
helm upgrade agentic-brain ./helm/agentic-brain \
  --set image.tag=v1.1.0

# Upgrade with new values
helm upgrade agentic-brain ./helm/agentic-brain \
  -f values-prod.yaml \
  --set neo4j.password=$NEO4J_PASSWORD
```

### Uninstall

```bash
helm uninstall agentic-brain --namespace agentic-brain
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_URI` | Yes | - | Neo4j connection URI |
| `NEO4J_PASSWORD` | Yes | - | Neo4j password |
| `REDIS_URL` | If redis | - | Redis connection URL |
| `JWT_SECRET` | If auth | - | JWT signing secret |
| `API_KEYS` | No | - | Comma-separated API keys |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `AUTH_ENABLED` | No | `true` | Enable authentication |

### Resource Recommendations

| Environment | Replicas | Memory | CPU |
|-------------|----------|--------|-----|
| Development | 1 | 128-256Mi | 50-250m |
| Staging | 2 | 256-512Mi | 100-500m |
| Production | 3-10 | 512Mi-1Gi | 250m-1000m |

---

## Cloud-Specific Notes

### Google Kubernetes Engine (GKE)

```bash
# Create cluster
gcloud container clusters create agentic-brain \
  --num-nodes=3 \
  --machine-type=e2-standard-2

# Get credentials
gcloud container clusters get-credentials agentic-brain

# Deploy
kubectl apply -k k8s/overlays/prod
```

### Amazon EKS

```bash
# Create cluster
eksctl create cluster \
  --name agentic-brain \
  --nodes 3 \
  --node-type t3.medium

# Deploy
kubectl apply -k k8s/overlays/prod
```

### Azure AKS

```bash
# Create cluster
az aks create \
  --resource-group agentic-brain-rg \
  --name agentic-brain \
  --node-count 3 \
  --node-vm-size Standard_DS2_v2

# Get credentials
az aks get-credentials --resource-group agentic-brain-rg --name agentic-brain

# Deploy
kubectl apply -k k8s/overlays/prod
```

### k3s (Lightweight)

```bash
# Install k3s
curl -sfL https://get.k3s.io | sh -

# Deploy
kubectl apply -k k8s/overlays/prod
```

---

## Monitoring

### Check Deployment Status

```bash
# Pods
kubectl get pods -n agentic-brain -l app=agentic-brain

# Logs
kubectl logs -n agentic-brain -l app=agentic-brain -f

# HPA status
kubectl get hpa -n agentic-brain

# Events
kubectl get events -n agentic-brain --sort-by='.lastTimestamp'
```

### Health Check

```bash
# Port forward
kubectl port-forward -n agentic-brain svc/agentic-brain 8000:8000

# Check health
curl http://localhost:8000/health
```

---

## Troubleshooting

### Pod Won't Start

```bash
# Check pod status
kubectl describe pod -n agentic-brain <pod-name>

# Check logs
kubectl logs -n agentic-brain <pod-name> --previous
```

### Connection Issues

```bash
# Check service
kubectl get svc -n agentic-brain

# Check endpoints
kubectl get endpoints -n agentic-brain

# Test DNS
kubectl run debug --rm -it --image=busybox -- nslookup agentic-brain.agentic-brain.svc.cluster.local
```

### Secret Issues

```bash
# Check secrets exist
kubectl get secrets -n agentic-brain

# Verify secret content (base64)
kubectl get secret agentic-brain-secrets -n agentic-brain -o jsonpath='{.data}'
```

---

## See Also

- [DEPLOYMENT.md](../docs/DEPLOYMENT.md) - Full deployment guide
- [Helm Chart](./helm/agentic-brain/) - Helm chart documentation
- [values.yaml](./helm/agentic-brain/values.yaml) - All configuration options
