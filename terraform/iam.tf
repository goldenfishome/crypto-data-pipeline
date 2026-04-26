# ── Redshift → S3 read access ─────────────────────────────────────────────────

resource "aws_iam_role" "redshift_s3" {
  name = "${var.project}-redshift-s3"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "redshift.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "redshift_s3" {
  name = "s3-read"
  role = aws_iam_role.redshift_s3.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.raw.arn,
        "${aws_s3_bucket.raw.arn}/*"
      ]
    }]
  })
}

# ── EC2 (Airflow) instance profile ────────────────────────────────────────────

resource "aws_iam_role" "ec2_airflow" {
  name = "${var.project}-ec2-airflow"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ec2_s3" {
  name = "s3-readwrite"
  role = aws_iam_role.ec2_airflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadObject"
      ]
      Resource = [
        aws_s3_bucket.raw.arn,
        "${aws_s3_bucket.raw.arn}/*",
        aws_s3_bucket.logs.arn,
        "${aws_s3_bucket.logs.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "ec2_cloudwatch" {
  name = "cloudwatch-logs"
  role = aws_iam_role.ec2_airflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_airflow" {
  name = "${var.project}-ec2-airflow"
  role = aws_iam_role.ec2_airflow.name
}
