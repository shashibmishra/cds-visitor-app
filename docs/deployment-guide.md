# Deployment Guide - Step-by-Step

## Prerequisites Checklist

- [ ] AWS account with appropriate IAM permissions
- [ ] Terraform installed (`>= 1.0`)
- [ ] kubectl configured for target cluster
- [ ] Docker CLI installed
- [ ] AWS CLI v2 configured with credentials
- [ ] GitLab runner set up (for CI/CD)

---

## Development Environment Deployment

### Step 1: Local Testing with Docker Compose

```bash
cd /Users/shashimishra/project/cds-visitor-app

# Build and start services
docker-compose up -d

# Verify services are running
docker-compose ps

# Test the application
curl http://127.0.0.1:5001/
curl http://127.0.0.1:5001/health

# View logs
docker-compose logs -f app
docker-compose logs -f redis

# Stop services
docker-compose down
```

### Step 2: Deploy to Dev EKS Cluster (AWS)

#### 2.1 Create VPC & Networking Infrastructure

```bash
cd terraform/envs/dev

# Initialize Terraform (sets up S3 backend)
terraform init

# Review changes
terraform plan -var-file=terraform.tfvars

# Apply infrastructure
terraform apply -auto-approve -var-file=terraform.tfvars
```

**Outputs to note**:
```
eks_cluster_name = "cds-eks-dev"
eks_cluster_endpoint = "https://..."
redis_endpoint = "redis.xxxxx.ng.0001.apse1.cache.amazonaws.com"
```

#### 2.2 Configure kubectl

```bash
# Update kubeconfig with new cluster
aws eks update-kubeconfig \
  --name cds-eks-dev \
  --region ap-southeast-1

# Verify connection
kubectl cluster-info
kubectl get nodes
```

#### 2.3 Create Kubernetes Namespace & Secrets

```bash
# Create namespace
kubectl create namespace cds

# Create Redis secret (with actual endpoint from Terraform output)
kubectl create secret generic redis-secret \
  --from-literal=host=redis.xxxxx.ng.0001.apse1.cache.amazonaws.com \
  --from-literal=port=6379 \
  -n cds

# Verify secret
kubectl get secret redis-secret -n cds -o yaml
```

#### 2.4 Deploy Application

```bash
# Push Docker image to ECR (created by Terraform)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/cds-visitor-app"

# Login to ECR
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin $ECR_REPO

# Build and push
docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest

# Update deployment manifest with image
sed -i "s|<IMAGE>|$ECR_REPO:latest|g" k8s/deployment.yaml

# Apply Kubernetes manifests
kubectl apply -f k8s/ -n cds

# Verify deployment
kubectl get pods -n cds
kubectl get svc -n cds
```

#### 2.5 Smoke Test

```bash
# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=visitor -n cds --timeout=300s

# Port-forward to test locally
kubectl port-forward svc/visitor-app 5001:80 -n cds &

# Test endpoints
curl http://127.0.0.1:5001/
curl http://127.0.0.1:5001/health

# Check logs
kubectl logs -l app=visitor -n cds --tail=50
```

---

## Production Environment Deployment

### Step 1: Create Production Infrastructure

```bash
cd terraform/envs/prod

# Initialize
terraform init

# Plan (ALWAYS review before applying to prod)
terraform plan -var-file=terraform.tfvars > tfplan.txt

# Review tfplan.txt carefully!

# Apply (requires manual approval)
terraform apply -var-file=terraform.tfvars
```

### Step 2: Configure Production Kubernetes

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name cds-eks-prod \
  --region ap-southeast-1

# Create namespace
kubectl create namespace prod

# Create Redis secret (with ElastiCache endpoint)
kubectl create secret generic redis-secret \
  --from-literal=host=redis-prod.xxxxx.apse1.cache.amazonaws.com \
  --from-literal=port=6379 \
  -n prod

# Create image pull secret for private registry
kubectl create secret docker-registry regcred \
  --docker-server=registry.gitlab.com \
  --docker-username=<gitlab-username> \
  --docker-password=<gitlab-token> \
  -n prod
```

### Step 3: Deploy Application via GitLab CI/CD

```bash
# Tag release (triggers production deployment)
git tag v1.0.0
git push origin v1.0.0

# Monitor pipeline in GitLab
# - Build stage: compiles Docker image
# - Scan stage: Trivy security scan
# - Test stage: runs unit tests
# - Deploy_prod stage: manual approval required (click in UI)
```

### Step 4: Post-Deployment Verification

```bash
# Verify all pods running
kubectl get pods -n prod -o wide
kubectl get svc,ingress -n prod

# Check ingress DNS
kubectl describe ingress visitor-ingress -n prod

# Test via ALB DNS
curl https://cds-visitor-prod.example.com/

# Monitor logs
kubectl logs -l app=visitor -n prod -f

# Check metrics
kubectl top pods -n prod
```

---

## Rollback Procedures

### Quick Rollback (Kubernetes)

If deployment has issues:

```bash
# Check rollout history
kubectl rollout history deployment/visitor-app -n prod

# Rollback to previous version
kubectl rollout undo deployment/visitor-app -n prod

# Verify pods are recovering
kubectl rollout status deployment/visitor-app -n prod
```

### Full Rollback (Terraform)

```bash
# View plan of reverting last change
terraform plan -destroy -var-file=terraform.tfvars

# Revert to previous state (if stored in S3 backend)
terraform state pull > backup.tfstate
terraform state push previous.tfstate  # Restore from backup

# Or manually sync back
```

---

## Monitoring Post-Deployment

### CloudWatch Dashboard

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name CDS-Visitor \
  --dashboard-body file://dashboard.json

# View metrics
aws cloudwatch get-metric-statistics \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistics Average \
  --start-time 2026-02-18T00:00:00Z \
  --end-time 2026-02-19T00:00:00Z \
  --period 3600
```

### Kubernetes Monitoring

```bash
# Resource requests vs usage
kubectl top nodes
kubectl top pods -n prod

# Events (errors/warnings)
kubectl get events -n prod --sort-by='.lastTimestamp'

# Pod logs aggregation
kubectl logs -n prod -l app=visitor --tail=100 --all-containers=true
```

### Manual Testing

```bash
# Load test with Apache Bench
ab -n 1000 -c 10 https://cds-visitor-prod.example.com/

# Check response times
curl -w "@curl-format.txt" https://cds-visitor-prod.example.com/

# Verify counter increments
for i in {1..5}; do curl https://cds-visitor-prod.example.com/; echo; done
```

---

## Cleanup (Tear Down)

### Remove Application

```bash
# Delete Kubernetes manifests
kubectl delete namespace cds
kubectl delete namespace prod

# Wait for resources to be released
kubectl get namespace  # Should not show cds or prod
```

### Remove Infrastructure

```bash
# Destroy Terraform-managed resources
cd terraform/envs/prod
terraform destroy -var-file=terraform.tfvars

# Destroy dev when ready
cd terraform/envs/dev
terraform destroy -var-file=terraform.tfvars

# Verify in AWS Console (EC2, EKS, ElastiCache)
```

---

## Troubleshooting Deployment Issues

### Issue: `terraform apply` fails due to insufficient permissions

**Fix**: Ensure AWS IAM user has policies:
- `AmazonEKSFullAccess`
- `AmazonVPCFullAccess`
- `ElastiCacheFullAccess`
- `IAMFullAccess`

### Issue: Pods stuck in `ContainerCreating`

```bash
kubectl describe pod <pod-name> -n cds
# Look for: image pull errors, node capacity issues

# Fix: check image exists in ECR
aws ecr describe-images --repository-name cds-visitor-app --region ap-southeast-1
```

### Issue: Requests timeout after deployment

```bash
# Verify ALB targets are healthy
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:... \
  --region ap-southeast-1

# Check security group rules
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=cds-visitor-\*
```

---

_Refer to main [README.md](../README.md) for more details._
