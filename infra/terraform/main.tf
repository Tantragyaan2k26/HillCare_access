terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "HillCare-Access"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

module "network" {
  source      = "./modules/network"
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

module "storage" {
  source      = "./modules/storage"
  environment = var.environment
}

module "db" {
  source             = "./modules/db"
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  app_sg_id          = module.network.app_sg_id
}

module "compute" {
  source             = "./modules/compute"
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  app_sg_id          = module.network.app_sg_id
  s3_bucket_arn      = module.storage.processed_bucket_arn
}
