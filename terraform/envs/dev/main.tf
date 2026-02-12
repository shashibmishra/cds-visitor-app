module "eks_dev" {
  source         = "../../modules"
  cluster_name   = "cds-eks-dev"
  vpc_id         = "vpc-xxxx"
  private_subnets = ["subnet-xxxx", "subnet-yyyy"]
}
