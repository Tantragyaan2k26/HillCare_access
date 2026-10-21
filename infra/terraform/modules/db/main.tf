variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "app_sg_id" { type = string }

resource "aws_db_subnet_group" "rds" {
  name       = "hillcare-${var.environment}-db-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "hillcare-${var.environment}-db-subnet-group" }
}

resource "aws_security_group" "db" {
  name        = "hillcare-${var.environment}-db-sg"
  description = "Access to RDS PostGIS only from app security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_sg_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "hillcare-${var.environment}-db"
  allocated_storage      = 50
  max_allocated_storage  = 200
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.medium"
  db_name                = "hillcare_db"
  username               = "hillcare_admin"
  manage_master_user_password = true
  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.db.id]
  skip_final_snapshot    = true
  storage_encrypted      = true
  deletion_protection    = false
}

output "db_endpoint" { value = aws_db_instance.postgres.endpoint }
