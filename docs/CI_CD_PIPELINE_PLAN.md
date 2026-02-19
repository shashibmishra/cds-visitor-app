# CI/CD Pipeline Plan - CDS Visitor Application

## 1. Choice of CI/CD Tool: GitLab CI/CD

### Reason for Selection

**Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.**

#### Key Advantages:

1. **Native Kubernetes Integration**
   - Seamless integration with EKS via kubectl commands
   - No additional agents required for cluster access
   - Built-in Kubernetes cluster management

2. **Container Registry**
   - GitLab Container Registry for Docker image storage
   - Private and secure image repository
   - Integrated with pipeline for automated image builds

3. **Multi-Environment Support**
   - Environment-specific variables and secrets
   - Easy promotion from dev → prod
   - Manual approval gates for production deployments

4. **Secret Management**
   - Secure storage for AWS credentials
   - Environment-specific masked variables
   - No exposure in logs or artifacts

5. **Cost-Effective**
   - Generous free tier with substantial CI/CD minutes
   - Shared runners available
   - Can use self-hosted runners for cost optimization

---

## 2. CI/CD Pipeline Stages

### Pipeline Flow Diagram

```
Developer Push
      ↓
┌─────────────────────────────────────────────────┐
│              BUILD STAGE                         │
│  - Build Docker image                            │
│  - Tag with commit SHA                           │
│  - Push to GitLab Container Registry             │
└─────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────┐
│              SCAN STAGE                          │
│  - Run Trivy security scanning                   │
│  - Check for vulnerabilities                     │
│  - Fail pipeline if critical issues found        │
└─────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────┐
│          DEPLOY_DEV STAGE                        │
│  - Update kubeconfig for dev cluster             │
│  - Deploy to dev EKS cluster                     │
│  - Automatic deployment on merit                 │
└─────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────┐
│        MANUAL APPROVAL REQUIRED                  │
│  - Review code and deployment in dev             │
│  - Verify testing results                        │
└─────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────┐
│         DEPLOY_PROD STAGE                        │
│  - Update kubeconfig for prod cluster            │
│  - Deploy to production EKS cluster              │
│  - Manual trigger only (when: manual)            │
└─────────────────────────────────────────────────┘
      ↓
   DEPLOYED ✓
```

---

## 3. Detailed Pipeline Configuration

### Stage 1: BUILD
```yaml
Purpose: Container image creation and registry push
Duration: ~3-5 minutes
Failure Handling: Pipeline fails, prevents progression
```

**Actions:**
- Builds Docker image from Dockerfile
- Tags with unique SHA identifier
- Pushes to GitLab Container Registry

---

### Stage 2: SCAN
```yaml
Purpose: Security vulnerability assessment
Duration: ~2-3 minutes
Failure Handling: Pipeline stops if critical vulnerabilities found
```

**Actions:**
- Runs Trivy security scanner on Docker image
- Scans for CVEs in layers and dependencies
- Generates security report

---

### Stage 3: DEPLOY_DEV
```yaml
Purpose: Automatic deployment to development environment
Duration: ~2-3 minutes
Environment: dev
Automatic: YES (runs automatically after scan passes)
```

**Actions:**
- Authenticates with AWS using credentials
- Updates kubeconfig for dev EKS cluster
- Updates kubectl deployment image
- Runs smoke tests

---

### Stage 4: DEPLOY_PROD
```yaml
Purpose: Manual production deployment
Duration: ~2-3 minutes
Environment: prod
Automatic: NO (requires manual trigger)
Approval: Required before execution
```

**Actions:**
- Updates kubeconfig for prod EKS cluster
- Deploys to production with zero-downtime strategy
- Monitors deployment status

---

## 4. Environment Variables and Secrets

### Required GitLab Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `AWS_ACCESS_KEY_ID` | Protected | AWS authentication |
| `AWS_SECRET_ACCESS_KEY` | Protected, Masked | AWS authentication |
| `AWS_REGION` | Protected | AWS region (ap-southeast-1) |
| `EKS_DEV_CLUSTER` | Protected | Dev cluster name |
| `EKS_PROD_CLUSTER` | Protected | Prod cluster name |

### Setup Steps:
1. Go to GitLab Project → Settings → CI/CD → Variables
2. Add each variable with Protected and Masked flags
3. Variables are injected at runtime and not exposed in logs

---

## 5. Deployment Strategy

### Blue-Green Deployment Pattern
- New version (green) deployed alongside current (blue)
- Traffic switched only after health checks pass
- Immediate rollback capability

### Rolling Update Strategy
```yaml
strategy: RollingUpdate
maxSurge: 1
maxUnavailable: 0
```
- One new pod at a time
- Maintains service availability
- Gradual rollout with automatic rollback on failures

---

## 6. How to Trigger the Pipeline

### Option 1: Automatic Trigger
```bash
git push origin feature-branch
# Pipeline automatically starts on all commits
```

### Option 2: Manual Trigger
1. Go to GitLab Project → CI/CD → Pipelines
2. Click "Run Pipeline"
3. Select branch
4. Click "Create pipeline"

### Option 3: Scheduled Trigger
1. Go to GitLab Project → CI/CD → Schedules
2. Create schedule for nightly deployments
3. Set frequency (daily, weekly, etc.)

---

## 7. Monitoring and Troubleshooting

### Pipeline Status Checks
- View real-time logs: GitLab → CI/CD → Pipelines → Pipeline ID
- Check stage status with detailed logs
- Download test reports and artifacts

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Build fails | Docker syntax error | Check Dockerfile syntax, test locally |
| Registry push fails | Auth token expired | Refresh GitLab CI/CD token |
| Deploy fails | Cluster unreachable | Verify AWS credentials and cluster status |
| Health check fails | App not ready | Check application logs in pods |

---

## 8. Security Best Practices

✓ **Pipeline Security Measures:**
- All secrets masked in logs
- Protected branches require review
- Deploy keys rotated regularly
- Audit logs for all deployments
- Immutable image tags with SHA
- Security scanning before deployment

---

## 9. Performance Optimization

### Caching Strategy
```yaml
cache:
  paths:
    - pip-cache/
    - node_modules/
  key: $CI_COMMIT_REF_SLUG
```

### Parallel Execution
- Multiple stages can run in parallel
- Reduced total pipeline time
- Better resource utilization

### Expected Pipeline Duration
- **Total Time:** 7-15 minutes
  - Build: 3-5 minutes
  - Scan: 2-3 minutes
  - Deploy Dev: 2-3 minutes
  - Deploy Prod: 2-3 minutes


