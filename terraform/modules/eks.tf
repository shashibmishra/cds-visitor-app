module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  cluster_name    = var.cluster_name
  cluster_version = "1.29"
  vpc_id          = var.vpc_id
  subnets         = var.private_subnets

  eks_managed_node_groups = {
    default = {
      desired_size   = 2
      max_size       = 5
      min_size       = 2
      instance_types = ["t3.medium"]
      capacity_type  = "SPOT"
    }
  }
}
