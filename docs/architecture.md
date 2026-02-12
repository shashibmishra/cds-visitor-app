# Production Architecture

## Edge
- Route53
- AWS Load Balancer Controller (ALB)
- HTTPS via ACM

## Compute
- Multi-AZ EKS
- Auto Scaling node groups (Spot + On-Demand)
- HPA for pods

## Data
- Amazon ElastiCache Redis (cluster mode disabled for simplicity)

## Security
- IAM Roles for Service Accounts (IRSA)
- Secrets Manager
- Private subnets for worker nodes

## CI/CD
- GitLab pipeline with dev → prod promotion
