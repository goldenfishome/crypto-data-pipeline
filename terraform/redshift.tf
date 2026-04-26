# ── Subnet group (Redshift Serverless requires 2+ subnets in different AZs) ───

resource "aws_redshiftserverless_namespace" "main" {
  namespace_name      = var.project
  db_name             = "crypto_pipeline"
  admin_username      = var.redshift_admin_user
  admin_user_password = var.redshift_admin_password
  iam_roles           = [aws_iam_role.redshift_s3.arn]
}

resource "aws_redshiftserverless_workgroup" "main" {
  namespace_name     = aws_redshiftserverless_namespace.main.namespace_name
  workgroup_name     = var.project
  base_capacity      = 8 # minimum RPUs — scales to 0 when idle
  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.redshift.id]

  # Not publicly accessible — reachable only from EC2 within the VPC
  publicly_accessible = false
}
