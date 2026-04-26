variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name — used as a prefix on all resource names"
  type        = string
  default     = "crypto-pipeline"
}

variable "redshift_admin_user" {
  description = "Redshift Serverless admin username"
  type        = string
}

variable "redshift_admin_password" {
  description = "Redshift Serverless admin password (min 8 chars, mixed case + number)"
  type        = string
  sensitive   = true
}

variable "my_ip" {
  description = "Your public IP in CIDR notation for SSH and Airflow UI access (e.g. 1.2.3.4/32)"
  type        = string
}

variable "ec2_key_pair_name" {
  description = "Name of an existing EC2 Key Pair for SSH access to the Airflow instance"
  type        = string
}
