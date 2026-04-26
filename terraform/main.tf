terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3 — create this bucket manually once before `terraform init`:
  #   aws s3 mb s3://crypto-pipeline-tf-state --region us-east-1
  #   aws s3api put-bucket-versioning \
  #     --bucket crypto-pipeline-tf-state \
  #     --versioning-configuration Status=Enabled
  backend "s3" {
    bucket = "crypto-pipeline-tf-state"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}
