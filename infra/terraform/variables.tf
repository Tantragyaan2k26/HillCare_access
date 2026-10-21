variable "aws_region" {
  description = "AWS Region for deployment (Mumbai for India data residency)"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}
