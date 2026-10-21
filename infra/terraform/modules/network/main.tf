variable "environment" { type = string }
variable "vpc_cidr" { type = string }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "hillcare-${var.environment}-vpc" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = count.index == 0 ? "ap-south-1a" : "ap-south-1b"
  map_public_ip_on_launch = true
  tags                    = { Name = "hillcare-${var.environment}-public-${count.index}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = count.index == 0 ? "ap-south-1a" : "ap-south-1b"
  tags              = { Name = "hillcare-${var.environment}-private-${count.index}" }
}

resource "aws_security_group" "app" {
  name        = "hillcare-${var.environment}-app-sg"
  description = "Security group for HillCare API and ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "app_sg_id" { value = aws_security_group.app.id }
