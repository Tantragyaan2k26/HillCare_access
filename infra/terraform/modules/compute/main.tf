variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "app_sg_id" { type = string }
variable "s3_bucket_arn" { type = string }

resource "aws_ecs_cluster" "main" {
  name = "hillcare-${var.environment}-cluster"
}

resource "aws_lb" "api" {
  name               = "hillcare-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.app_sg_id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "hillcare-${var.environment}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/v1/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "alb_dns_name" { value = aws_lb.api.dns_name }
