variable "environment" { type = string }

resource "aws_s3_bucket" "raw" {
  bucket = "hillcare-raw-${var.environment}"
}

resource "aws_s3_bucket" "processed" {
  bucket = "hillcare-processed-${var.environment}"
}

resource "aws_s3_bucket" "public" {
  bucket = "hillcare-public-${var.environment}"
}

resource "aws_s3_bucket_versioning" "raw_versioning" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration {
    status = "Enabled"
  }
}

output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "processed_bucket" { value = aws_s3_bucket.processed.id }
output "processed_bucket_arn" { value = aws_s3_bucket.processed.arn }
output "public_bucket" { value = aws_s3_bucket.public.id }
