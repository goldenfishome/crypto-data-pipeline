output "ec2_public_ip" {
  description = "Public IP of the Airflow EC2 instance"
  value       = aws_instance.airflow.public_ip
}

output "redshift_endpoint" {
  description = "Redshift Serverless endpoint hostname"
  value       = aws_redshiftserverless_workgroup.main.endpoint[0].address
}

output "raw_bucket_name" {
  description = "S3 bucket for raw Parquet files"
  value       = aws_s3_bucket.raw.bucket
}

output "redshift_iam_role_arn" {
  description = "IAM role ARN for REDSHIFT_IAM_ROLE in .env"
  value       = aws_iam_role.redshift_s3.arn
}

output "ssh_command" {
  description = "Ready-to-use SSH command for the Airflow instance"
  value       = "ssh -i ~/.ssh/${var.ec2_key_pair_name}.pem ec2-user@${aws_instance.airflow.public_ip}"
}
