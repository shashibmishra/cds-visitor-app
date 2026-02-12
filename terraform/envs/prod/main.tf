module "eks_prod" {
  source         = "../../modules"
  cluster_name   = "cds-eks-prod"
  vpc_id         = "vpc-xxxx"
  private_subnets = ["subnet-xxxx", "subnet-yyyy"]
}
