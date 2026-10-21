output "vpc_id" {
  value = module.network.vpc_id
}

output "db_endpoint" {
  value = module.db.db_endpoint
}

output "alb_dns_name" {
  value = module.compute.alb_dns_name
}

output "processed_s3_bucket" {
  value = module.storage.processed_bucket
}
