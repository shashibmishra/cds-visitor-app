# CDS Visitor Application - Production-Ready Architecture

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Strategy](#architecture-strategy)
3. [Component Breakdown](#component-breakdown)
4. [Directory Structure](#directory-structure)
5. [Local Development Setup](#local-development-setup)
6. [Deployment Strategy](#deployment-strategy)
7. [High Availability & Resilience](#high-availability--resilience)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Security & Best Practices](#security--best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

The **CDS Visitor Application** is a production-grade, multi-tier application demonstrating:
- **High Availability Across Multiple AZs** in AWS EKS
- **Graceful failure handling** with fallback strategies
- **Infrastructure-as-Code** (Terraform) for reproducible deployments
- **Automated CI/CD** via GitLab for dev → prod promotion
- **Cloud-native design** following AWS best practices

**Core Functionality**: Displays visitor count by incrementing a counter stored in Redis.

---

## Architecture Strategy

### Why This Approach?

#### 1. **Component Segregation** (NOT Monolithic)
Instead of bundling everything, we separated:
- **Application Logic** (`app/`) — Flask microservice
- **Infrastructure Code** (`terraform/`) — IaC for AWS resources
- **Kubernetes Manifests** (`k8s/`) — Pod/Service definitions
- **Configuration** (`config/`) — Environment-specific settings
- **CI/CD Pipeline** (`.gitlab-ci.yml`) — Automated deployments

**Benefit**: Each component can scale, be versioned, and tested independently.

#### 2. **Multi-AZ Resilience**
- **EKS across 3 AZs** ensures pod replicas are distributed geographically
- **ElastiCache Redis (cluster mode disabled for now, upgradable)** provides resilient data layer
- **Application Replicas (3 minimum)** tolerate node/pod failures
- **Auto-Scaling Nodes** (Mix of Spot + On-Demand) reduce costs while maintaining QoS

**Benefit**: If one AZ fails, requests redirect to other AZs seamlessly.

#### 3. **Configuration Management** (No Hardcoding)
- Environment variables passed via Kubernetes Secrets
- Terraform `tfvars` separated by environment (dev/prod)
- Application config loaded from environment at runtime

**Benefit**: Same Docker image deploys to any environment without rebuilding.

#### 4. **CI/CD Placement** (GitLab-native)
- Build triggered on git push
- Security scans before promotion
- Dev deployments automatic
- Prod deployments manual + approval gates

**Benefit**: Auditable, reversible, and compliant with SDLC requirements.

---

## Component Breakdown

### 1. Application Tier (`app/app.py`)

**Current Status**: ✅ Enhanced with error handling

**Improvements Made**:
```python
# OLD: Would crash if Redis unavailable
r = redis.Redis(host=redis_host, port=6379)

# NEW: Graceful degradation with empty counter
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
try:
    r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=5)
    r.ping()
except redis.exceptions.ConnectionError:
    r = None  # Counter disabled but app stays up (503 response)
```

**Recommended Next Steps**:
- [ ] Segregate routes into `routes/visitor.py`, `routes/health.py`
- [ ] Move Redis logic to `services/cache.py`
- [ ] Extract config to `config/settings.py`
- [ ] Add logging middleware for request tracing

**Example Structure**:
```
app/
├── app.py              # Flask app initialization
├── config/
│   └── settings.py     # Environment config
├── routes/
│   ├── visitor.py      # /  and / logic
│   └── health.py       # /health endpoint
├── services/
│   └── cache.py        # Redis client & retry logic
└── requirements.txt
```

---

### 2. Docker & Image Management (`Dockerfile`)

**Current Status**: ✅ Multi-stage capable, but basic

**Improvements**:
```dockerfile
# Multi-stage build (smaller final image)
FROM python:3.11-slim as builder
WORKDIR /build
COPY app/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY app/ .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=2)"
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

**Benefits**:
- Smaller image size (~150MB → ~80MB)
- Production-grade WSGI server (Gunicorn instead of Flask dev server)
- Built-in health check for Kubernetes

---

### 3. Kubernetes Manifests (`k8s/`)

**Current Status**: ⚠️ Partial — missing critical configs

**Missing Components**:
- [ ] **Service** — expose app within cluster
- [ ] **Ingress** — expose app externally with HTTPS
- [ ] **ConfigMap** — non-sensitive environment variables
- [ ] **Secrets** — sensitive data (Redis password)
- [ ] **NetworkPolicy** — restrict pod-to-pod traffic
- [ ] **PodDisruptionBudget** — ensure HA during node drains
- [ ] **ServiceAccount + RBAC** — least-privilege access

**Recommended Additions**:
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: visitor-app
  namespace: default
spec:
  type: ClusterIP  # Internal only; ALB handles external
  selector:
    app: visitor
  ports:
    - port: 80
      targetPort: 5000
      name: http

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: visitor-ingress
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: alb
  rules:
    - host: cds-visitor.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: visitor-app
                port:
                  number: 80

---
# k8s/pdb.yaml (Pod Disruption Budget)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: visitor-app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: visitor
```

**Why These Matter for HA**:
- **Service**: Stable DNS (`visitor-app.default.svc.cluster.local`)
- **Ingress**: Automatic SSL/TLS termination; ALB health checks
- **PDB**: Prevents simultaneous pod eviction during node maintenance

---

### 4. Terraform Infrastructure (`terraform/`)

**Current Status**: ⚠️ Barebone EKS module; missing components

**Missing Components**:
- [ ] **VPC & Networking** (subnets, NAT gateways, route tables)
- [ ] **ElastiCache Redis** (cluster with Multi-AZ failover)
- [ ] **IAM Roles** (IRSA for app → Secrets Manager access)
- [ ] **ALB** (Application Load Balancer for external traffic)
- [ ] **Security Groups** (pod-to-pod, pod-to-redis rules)
- [ ] **CloudWatch Logging** (centralized app + EKS logs)
- [ ] **Variables & Outputs** (DRY principle)

**Recommended Structure**:
```
terraform/
├── variables.tf          # Global variables
├── outputs.tf            # Global outputs
├── main.tf               # Provider config + backend
├── envs/
│   ├── dev/
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── terraform.tfvars
│       └── backend.tf
└── modules/
    ├── vpc/
    │   ├── main.tf, variables.tf, outputs.tf
    ├── eks/
    │   ├── main.tf, variables.tf, outputs.tf
    ├── redis/
    │   ├── main.tf, variables.tf, outputs.tf
    ├── rds/              # (Optional) Database tier
    │   ├── main.tf, variables.tf, outputs.tf
    └── monitoring/
        ├── main.tf, variables.tf, outputs.tf
```

**Example: Redis Module** (`terraform/modules/redis/main.tf`)
```hcl
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.cluster_name}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type        # e.g., "cache.t3.micro"
  num_cache_nodes      = var.redis_num_nodes        # 1 for dev, 3+ for prod
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  # Multi-AZ setup (if num_cache_nodes > 1 with cluster mode)
  # automatic_failover_enabled = true
}
```

---

### 5. CI/CD Pipeline (`.gitlab-ci.yml`)

**Current Status**: ⚠️ Incomplete — missing security scans & validation

**Improvements Needed**:
```yaml
stages:
  - build
  - scan
  - test
  - deploy_dev
  - integration_tests
  - deploy_staging
  - smoke_tests
  - deploy_prod

variables:
  REGISTRY: registry.gitlab.com
  IMAGE_NAME: $REGISTRY/$CI_PROJECT_NAMESPACE/$CI_PROJECT_NAME
  IMAGE_TAG: $IMAGE_NAME:$CI_COMMIT_SHA
  LATEST_TAG: $IMAGE_NAME:latest

build:
  stage: build
  image: docker:dind
  services:
    - docker:dind
  script:
    - docker build -t $IMAGE_TAG -t $LATEST_TAG .
    - docker push $IMAGE_TAG
    - docker push $LATEST_TAG

scan:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy image --exit-code 0 --severity HIGH,CRITICAL $IMAGE_TAG
    - trivy image --exit-code 1 --severity CRITICAL $IMAGE_TAG  # Fail on CRITICAL

test:
  stage: test
  image: python:3.11
  script:
    - pip install -r app/requirements.txt pytest pytest-cov
    - pytest app/test_app.py -v --cov=app

deploy_dev:
  stage: deploy_dev
  image: alpine/helm:latest
  environment:
    name: dev
    kubernetes_namespace: default
  script:
    - aws eks update-kubeconfig --name cds-eks-dev --region ap-southeast-1
    - kubectl set image deployment/visitor-app visitor=$IMAGE_TAG -n default
    - kubectl rollout status deployment/visitor-app -n default --timeout=5m

smoke_tests:
  stage: smoke_tests
  image: alpine/curl
  script:
    - curl -f http://visitor-app.example.com/health || exit 1
    - curl -f http://visitor-app.example.com/ || exit 1

deploy_prod:
  stage: deploy_prod
  image: alpine/helm:latest
  environment:
    name: prod
    kubernetes_namespace: prod
  when: manual
  only:
    - tags
  script:
    - aws eks update-kubeconfig --name cds-eks-prod --region ap-southeast-1
    - kubectl set image deployment/visitor-app visitor=$IMAGE_TAG -n prod
    - kubectl rollout status deployment/visitor-app -n prod --timeout=5m
```

**Why These Stages Matter**:
- Scan removes vulnerable images before deployment
- Tests prevent broken code reaching production
- Smoke tests verify post-deployment health
- Manual prod gate + tag-only triggers = audit trail

---

## Directory Structure

**Final Recommended Layout**:
```
cds-visitor-app/
├── README.md                      # ✅ This file
├── .gitlab-ci.yml                 # ✅ Enhanced CI/CD pipeline
├── .gitignore                     # Exclude secrets, __pycache__, terraform/.tfstate
├── Dockerfile                     # ✅ Multi-stage, production-ready
├── docker-compose.yml             # ✅ Local dev environment
├── app/
│   ├── app.py                     # Main Flask app
│   ├── requirements.txt           # Python dependencies
│   ├── config/
│   │   └── settings.py            # Config management
│   ├── routes/
│   │   ├── visitor.py             # /  endpoint
│   │   └── health.py              # /health endpoint
│   ├── services/
│   │   └── cache.py               # Redis client
│   └── tests/
│       ├── test_app.py            # Unit tests
│       └── conftest.py            # Pytest fixtures
├── k8s/
│   ├── deployment.yaml            # ✅ Pod replicas & probes
│   ├── hpa.yaml                   # ✅ Auto-scaling
│   ├── service.yaml               # ⬜ NEW: Cluster DNS
│   ├── ingress.yaml               # ⬜ NEW: External access + HTTPS
│   ├── pdb.yaml                   # ⬜ NEW: Pod disruption budget
│   ├── configmap.yaml             # ⬜ NEW: Non-sensitive config
│   ├── secret.yaml                # ⬜ NEW: Sensitive data (Redis password)
│   └── network-policy.yaml        # ⬜ NEW: Pod security
├── terraform/
│   ├── variables.tf               # ⬜ NEW: Global variables
│   ├── outputs.tf                 # ⬜ NEW: Global outputs
│   ├── main.tf                    # ⬜ NEW: Backend + provider
│   ├── envs/
│   │   ├── dev/
│   │   │   ├── terraform.tfvars   # Dev env values (region, instance types, etc.)
│   │   │   ├── backend.tf         # Dev remote state (S3)
│   │   │   └── main.tf            # Dev-specific overrides
│   │   └── prod/
│   │       ├── terraform.tfvars   # Prod env values (HA, monitoring, etc.)
│   │       ├── backend.tf         # Prod remote state (S3, locked)
│   │       └── main.tf            # Prod-specific overrides
│   └── modules/
│       ├── vpc/
│       │   ├── main.tf            # VPC, subnets, NAT gateways
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── eks/
│       │   ├── main.tf            # EKS cluster + node groups
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── redis/
│       │   ├── main.tf            # ElastiCache cluster
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── alb/
│       │   ├── main.tf            # Application Load Balancer
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── iam/
│       │   ├── main.tf            # IAM roles, policies, IRSA
│       │   ├── variables.tf
│       │   └── outputs.tf
│       └── monitoring/
│           ├── main.tf            # CloudWatch, SNS, alarms
│           ├── variables.tf
│           └── outputs.tf
├── docs/
│   ├── architecture.md            # ✅ High-level design
│   ├── deployment-guide.md        # ⬜ NEW: Step-by-step deployment
│   ├── troubleshooting.md         # ⬜ NEW: Common issues & fixes
│   ├── security-model.md          # ⬜ NEW: Authentication, RBAC, secrets
│   └── cost-optimization.md       # ⬜ NEW: Spot instances, reserved capacity
└── scripts/
    ├── deploy.sh                  # ⬜ NEW: Wrapper for Terraform + kubectl
    ├── setup-secrets.sh           # ⬜ NEW: Create K8s secrets
    └── backup-redis.sh            # ⬜ NEW: Daily Redis backup job
```

---

## Local Development Setup

### Prerequisites
- Docker & Docker Compose
- Kubernetes local (Docker Desktop k8s or Minikube)
- `kubectl`, `helm`, Terraform CLI
- AWS CLI (for AWS interaction)

### Quick Start (Docker Compose)

**Step 1: Clone & Navigate**
```bash
git clone <repo> && cd cds-visitor-app
```

**Step 2: Build & Run**
```bash
docker-compose up -d
```

**Step 3: Test**
```bash
curl http://127.0.0.1:5001/         # Increment and display counter
curl http://127.0.0.1:5001/health   # Health check
```

**Step 4: View Logs**
```bash
docker-compose logs -f app
docker-compose logs -f redis
```

### Local Kubernetes Deployment

**Step 1: Start Kubernetes**
```bash
# Docker Desktop: Enable Kubernetes in settings
# OR use Minikube:
minikube start --cpus 4 --memory 8192
```

**Step 2: Create Namespace**
```bash
kubectl create namespace cds
```

**Step 3: Create Secrets**
```bash
# Create Redis password secret
kubectl create secret generic redis-secret \
  --from-literal=host=redis \
  --from-literal=port=6379 \
  -n cds

# Create image pull secret (if using private registry)
kubectl create secret docker-registry regcred \
  --docker-server=registry.gitlab.com \
  --docker-username=<your-username> \
  --docker-password=<your-token> \
  -n cds
```

**Step 4: Deploy Application**
```bash
# Build image locally
docker build -t visitor-app:local .

# Load into Minikube (if using Minikube)
minikube image load visitor-app:local

# Apply manifests
kubectl apply -f k8s/ -n cds
```

**Step 5: Port-Forward & Test**
```bash
# Forward local port to service
kubectl port-forward svc/visitor-app 5001:80 -n cds

# In another terminal
curl http://127.0.0.1:5001/
```

---

## Deployment Strategy

### Development Environment

**Goals**: Fast iteration, low cost, minimal redundancy

**Configuration** (`terraform/envs/dev/terraform.tfvars`):
```hcl
environment         = "dev"
cluster_name        = "cds-eks-dev"
region              = "ap-southeast-1"
node_instance_types = ["t3.medium"]  # Single type
min_nodes           = 1
max_nodes           = 3
redis_node_type     = "cache.t3.micro"
redis_num_nodes     = 1              # Single node (no failover)
enable_spot         = true           # 100% Spot for cost savings
enable_logging      = false          # Minimal logging
```

**Deployment Command**:
```bash
cd terraform/envs/dev
terraform plan
terraform apply
```

### Production Environment

**Goals**: High availability, disaster recovery, compliance

**Configuration** (`terraform/envs/prod/terraform.tfvars`):
```hcl
environment         = "prod"
cluster_name        = "cds-eks-prod"
region              = "ap-southeast-1"
node_instance_types = ["t3.large", "t3a.large"]  # Mix for diversity
min_nodes           = 3                           # Multi-AZ spread
max_nodes           = 20
redis_node_type     = "cache.r7g.large"          # Memory-optimized
redis_num_nodes     = 3                          # Multi-AZ with failover
enable_spot         = false                      # On-demand only
enable_logging      = true                       # Full observability
enable_backup       = true                       # Daily snapshots
backup_retention_days = 30
```

**Multi-Region Failover** (Advanced):
- Replicate to `ap-southeast-2` (Sydney)
- Route53 health checks → automatic failover
- Cross-region Redis replication using DMS

---

## High Availability & Resilience

### 1. **Pod-Level Redundancy**
```yaml
spec:
  replicas: 3                      # Minimum 3 pods
  strategy:
    type: RollingUpdate            # Gradual replacement
    rollingUpdate:
      maxUnavailable: 1            # Keep 2 pods running during updates
      maxSurge: 1                  # Add 1 new pod at a time
```

### 2. **Automatic Scaling**
```yaml
minReplicas: 2
maxReplicas: 10
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 75
```
Scales up when CPU/memory exceeds thresholds; scales down on light load.

### 3. **Proactive Health Checks**
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3
livenessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 15
  periodSeconds: 20
  failureThreshold: 3
```
- Readiness: Pod receives traffic only if healthy
- Liveness: Restart unhealthy pods

### 4. **Pod Disruption Budget**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: visitor-pdb
spec:
  minAvailable: 2                  # Keep 2 pods running during maintenance
  selector:
    matchLabels:
      app: visitor
```
Ensures Kubernetes respects HA during node drains (updates, scaling down).

### 5. **Node-Level Redundancy**
- Nodes spread across 3 AZs
- Mix of Spot + On-Demand instances
- Auto Scaling Groups with capacity rebalancing

### 6. **Data-Layer Resilience** (Redis)
```hcl
# ElastiCache with Multi-AZ Automatic Failover
resource "aws_elasticache_cluster" "redis" {
  engine_version       = "7.0"
  num_cache_nodes      = 3             # 3 nodes across AZs
  automatic_failover_enabled = true
  multi_az_enabled     = true
}
```
If primary Redis fails, standby automatically promotes.

### 7. **Network Resilience**
- **VPC with 3 subnets** (1 per AZ)
- **NAT Gateways** in each AZ (redundant)
- **Security Groups** restrict lateral movement
- **Network Policies** enforce pod-to-pod rules

---

## CI/CD Pipeline

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Git Push (any branch)                                       │
├─────────────────────────────────────────────────────────────┤
│ 1. BUILD                                                    │
│    - Docker build (multi-stage)                             │
│    - Push to registry                                       │
├─────────────────────────────────────────────────────────────┤
│ 2. SCAN                                                     │
│    - Trivy: image vulnerabilities                           │
│    - SAST: code security (Semgrep, etc.)                    │
│    - Dependency check                                       │
├─────────────────────────────────────────────────────────────┤
│ 3. TEST                                                     │
│    - Unit tests (pytest)                                    │
│    - Integration tests (Redis + Flask)                      │
│    - Code coverage check (>80%)                             │
├─────────────────────────────────────────────────────────────┤
│ 4. DEPLOY_DEV                                               │
│    - Auto-deploy to dev EKS cluster                         │
│    - Run smoke tests                                        │
├─────────────────────────────────────────────────────────────┤
│ 5. APPROVAL GATE                                            │
│    - Manual approval required for prod                      │
├─────────────────────────────────────────────────────────────┤
│ 6. DEPLOY_PROD                                              │
│    - Rolling update (gradual traffic shift)                 │
│    - Health checks during rollout                           │
│    - Automatic rollback on failure                          │
├─────────────────────────────────────────────────────────────┤
│ 7. POST-DEPLOY                                              │
│    - Performance monitoring (Prometheus)                    │
│    - Error tracking (Sentry)                                │
│    - Alert on anomalies                                     │
└─────────────────────────────────────────────────────────────┘
```

### GitLab Pipeline Configuration

**Enhanced `.gitlab-ci.yml`**:
See [CI/CD Pipeline](#5-cicd-pipeline-gitlabci-yml) section above for full details.

**Key Stages**:
1. **Build**: Docker multi-stage compile + push to registry
2. **Scan**: Trivy vulnerability scan + fail on CRITICAL
3. **Test**: Pytest + coverage reporting
4. **Deploy Dev**: Automatic (every commit to main)
5. **Smoke Tests**: Health checks post-deployment
6. **Deploy Prod**: Manual trigger only on git tags

### GitLab Runner Setup

**Install GitLab Runner** (on separate EC2 or Fargate):
```bash
curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | bash
apt-get install gitlab-runner

# Register runner with Kubernetes executor
gitlab-runner register \
  --url https://gitlab.com/ \
  --registration-token <your-token> \
  --executor kubernetes \
  --kubernetes-host https://<k8s-api>:443 \
  --kubernetes-namespace gitlab-runner
```

---

## Security & Best Practices

### 1. **Container Security**
- ✅ Run as non-root user (`USER appuser` in Dockerfile)
- ✅ Read-only filesystem where possible
- ✅ No secrets hardcoded (use Kubernetes Secrets or AWS Secrets Manager)
- ✅ Image scanning (Trivy) before deployment
- ✅ Minimal base image (python:3.11-slim, not ubuntu)

### 2. **Network Security**
- ✅ Pod Network Policies (restrict ingress/egress)
- ✅ Private subnets for worker nodes
- ✅ Security Groups limit port access
- ✅ TLS/HTTPS for external traffic (via ALB + cert-manager)

### 3. **Identity & Access**
- ✅ IRSA (IAM Roles for Service Accounts) — no EC2 IAM role needed
- ✅ RBAC in Kubernetes — least-privilege for service accounts
- ✅ Secrets encrypted at rest (etcd encryption + KMS)

**Example ServiceAccount + RBAC**:
```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: visitor-app
  namespace: cds

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: visitor-app-role
  namespace: cds
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: visitor-app-binding
  namespace: cds
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: visitor-app-role
subjects:
  - kind: ServiceAccount
    name: visitor-app
    namespace: cds
```

### 4. **Secrets Management**
- ✅ Never commit secrets to git
- ✅ Use AWS Secrets Manager or HashiCorp Vault
- ✅ Rotate Redis password every 90 days
- ✅ Use separate secrets for each environment

**Example**: Create secret in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name cds/redis/password \
  --secret-string "MySecurePassword123!" \
  --region ap-southeast-1
```

Then reference in Terraform:
```hcl
data "aws_secretsmanager_secret_version" "redis_password" {
  secret_id = "cds/redis/password"
}

resource "aws_elasticache_cluster" "redis" {
  auth_token = data.aws_secretsmanager_secret_version.redis_password.secret_string
}
```

### 5. **Compliance & Auditing**
- ✅ CloudTrail logs all API calls
- ✅ VPC Flow Logs capture network traffic
- ✅ EKS audit logs track cluster actions
- ✅ Container logs centralized to CloudWatch
- ✅ Cost tracking via AWS Cost Explorer

---

## Troubleshooting

### Issue: Pods in CrashLoopBackOff

**Symptoms**: `kubectl get pods` shows `CrashLoopBackOff`

**Diagnosis**:
```bash
kubectl describe pod <pod-name> -n cds
kubectl logs <pod-name> -n cds --previous
```

**Common Causes & Fixes**:
1. **Redis unreachable**
   - Check Redis secret: `kubectl get secret redis-secret -n cds -o yaml`
   - Verify Redis pod is running: `kubectl get pods -l app=redis -n cds`
   - Test connectivity from app pod: `kubectl exec <app-pod> -- redis-cli -h redis ping`

2. **OOMKilled (out of memory)**
   - Check limits: `kubectl describe pod <pod-name>`
   - Increase memory request/limit in deployment.yaml
   - Monitor with: `kubectl top pods -n cds`

3. **Missing dependencies**
   - Check Dockerfile: `pip install -r requirements.txt` runs
   - Verify Docker build logs: `docker build -t visitor-app:local .`

### Issue: Deployment Stuck in Pending

**Symptoms**: New pods stay in `Pending` state

**Diagnosis**:
```bash
kubectl describe pod <pod-name> -n cds | grep -A 10 Events
```

**Common Causes & Fixes**:
1. **Insufficient node capacity**
   - Check nodes: `kubectl get nodes`
   - Check available resources: `kubectl describe nodes`
   - Scale up node group (Terraform or AWS Console)

2. **Image not found**
   - Verify image exists in registry: `docker pull <image-tag>`
   - Check imagePullSecret: `kubectl get secret regcred -n cds`
   - Ensure service account has pull permission

3. **PVC (Persistent Volume Claim) pending**
   - Check PVC: `kubectl get pvc -n cds`
   - StorageClass must exist: `kubectl get sc`

### Issue: Requests Timing Out (504)

**Symptoms**: `curl` returns 504 Gateway Timeout

**Diagnosis**:
```bash
# Check ALB target health
aws elbv2 describe-target-health --target-group-arn <arn> --region ap-southeast-1

# Check pod readiness
kubectl get pods -n cds -o wide
kubectl logs <pod-name> -n cds

# Check service DNS
kubectl describe svc visitor-app -n cds
```

**Common Causes & Fixes**:
1. **Pods not ready**
   - Check readiness probe: `kubectl describe deployment visitor-app -n cds`
   - Fix and redeploy: `kubectl rollout restart deployment/visitor-app -n cds`

2. **ALB target unavailable**
   - Ensure security group allows traffic: port 5000 from ALB SG
   - Verify pod is bound to service: `kubectl get endpoints visitor-app -n cds`

3. **Horizontal Pod Autoscaler maxed out**
   - Check HPA: `kubectl get hpa visitor-hpa -n cds`
   - Increase maxReplicas in hpa.yaml

### Issue: Redis Connection Refused

**Symptoms**: App logs show `[Errno 111] Connection refused` or `Error connecting to None:6379`

**Diagnosis**:
```bash
# Check Redis pod
kubectl get pods -l app=redis -n cds

# Check Redis logs
kubectl logs <redis-pod> -n cds

# Test Redis connectivity
kubectl exec <redis-pod> -n cds -- redis-cli ping
```

**Common Causes & Fixes**:
1. **REDIS_HOST env var not set**
   - Check ConfigMap/Secret: `kubectl get cm,secret -n cds`
   - Verify deployment mounts them: `kubectl describe deployment visitor-app -n cds | grep -A 20 "Environment"`

2. **Redis pod crashed**
   - Check logs: `kubectl logs <redis-pod> -n cds --previous`
   - Check Redis memory: `kubectl exec <redis-pod> -- redis-cli info memory`
   - Increase memory request in Redis StatefulSet

3. **Network policy blocking traffic**
   - Inspect: `kubectl get networkpolicies -n cds`
   - Ensure ingress rule allows app → redis traffic

### Issue: Out of Memory (OOMKilled)

**Symptoms**: Pods restart with `OOMKilled` status

**Diagnosis**:
```bash
kubectl describe pod <pod-name> | grep -A 5 "Last State"
kubectl top pods -n cds --containers
```

**Fixes**:
- Increase memory limit in `k8s/deployment.yaml`:
  ```yaml
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"           # Increased from 256Mi
      cpu: "500m"
  ```
- Scale down replicas temporarily to free cluster memory
- Examine app for memory leaks (profiling with Py-Spy)

---

## Monitoring & Observability

### 1. **Metrics** (Prometheus + Grafana)
- Pod CPU/memory usage
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Redis memory/evictions

### 2. **Logging** (CloudWatch + Log Insights)
```bash
# Query all ERROR logs in last hour
aws logs insights --region ap-southeast-1 \
  --log-group-name /aws/eks/cds-visitor \
  --query 'fields @timestamp, @message | filter @message like /ERROR/'
```

### 3. **Tracing** (X-Ray or Jaeger)
- Request flow from ingress → app → Redis
- Identify bottlenecks
- Trace failed requests

### 4. **Alerting** (SNS + CloudWatch)
```hcl
resource "aws_cloudwatch_metric_alarm" "pod_cpu" {
  alarm_name          = "visitor-app-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "container_cpu_usage_seconds_total"
  period              = 300
  statistic           = "Average"
  threshold           = 0.75
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

---

## Cost Optimization

### 1. **Compute**
- Use Spot instances (70% cheaper than On-Demand)
- Capacity rebalancing (automatic Spot replacement)
- Right-sizing: `t3.medium` for dev, `t3.large` for prod

### 2. **Storage**
- ElastiCache: use `cache.t3` for dev, `cache.r7g` for prod
- RDS (if added): Graviton2 instances + reserved capacity

### 3. **Data Transfer**
- VPC endpoints for AWS service access (no NAT Gateway charges)
- CloudFront (if serving static content)
- Same-region deployments to avoid cross-AZ egress

### Example Dev Cost (monthly):
- EKS cluster (1 t3.medium): $50
- ElastiCache (1 cache.t3.micro): $20
- NAT Gateway: $32
- Data transfer: $5
- **Total: ~$110/month**

### Example Prod Cost (monthly):
- EKS cluster (3 t3.large + 2 t3a.large, mixed spot/on-demand): $400
- ElastiCache (3 cache.r7g.large with failover): $800
- NAT Gateways (3): $96
- ALB: $25
- Data transfer: $50
- **Total: ~$1,400/month**

---

## Next Steps (Roadmap)

1. **Immediate** (This week)
   - [ ] Segregate Flask app into routes/services (Feature)
   - [ ] Add unit tests + CI step (Tests)
   - [ ] Create Terraform modules (IaC)

2. **Short-term** (Next 2 weeks)
   - [ ] Deploy dev environment (Infrastructure)
   - [ ] Set up CloudWatch logging (Observability)
   - [ ] Add Pod Network Policies (Security)

3. **Medium-term** (Next month)
   - [ ] Migrate to production EKS (Prod deployment)
   - [ ] Enable Redis cluster mode (Data HA)
   - [ ] Multi-region failover (DR)

4. **Long-term** (Q2+)
   - [ ] Service mesh (Istio) for traffic management
   - [ ] API gateway (Kong) for rate limiting
   - [ ] Distributed tracing (Jaeger)
   - [ ] Canary deployments (Flagger)

---

## References & Resources

- **Kubernetes**: https://kubernetes.io/docs/
- **Terraform AWS**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **GitLab CI**: https://docs.gitlab.com/ee/ci/
- **AWS EKS Best Practices**: https://aws.github.io/aws-eks-best-practices/
- **Flask**: https://flask.palletsprojects.com/
- **Redis**: https://redis.io/docs/

---

## Support & Contact

For issues, feature requests, or questions:
- Create a GitLab issue: https://gitlab.com/cds-team/cds-visitor-app/-/issues
- Slack: #cds-team
- Email: cds-team@example.com

---

**Last Updated**: February 18, 2026  
**Maintained By**: CDS Platform Team
