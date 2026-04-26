# ── Latest Amazon Linux 2023 AMI ─────────────────────────────────────────────

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── EC2 instance: self-hosted Airflow ─────────────────────────────────────────

resource "aws_instance" "airflow" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_airflow.name
  key_name               = var.ec2_key_pair_name

  root_block_device {
    volume_size = 20 # GB — enough for Docker images + logs
    volume_type = "gp3"
  }

  # Bootstrap script: installs Docker + Docker Compose on first boot.
  # After SSH-ing in, clone the repo, fill in .env, and run `docker compose up -d`.
  user_data = <<-EOF
    #!/bin/bash
    set -e

    dnf update -y
    dnf install -y docker git

    systemctl start docker
    systemctl enable docker
    usermod -aG docker ec2-user

    # Docker Compose v2 plugin
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    echo "Bootstrap complete — SSH in and run: git clone <your-repo> && cd crypto-data-pipeline && cp .env.example .env" \
      > /home/ec2-user/NEXT_STEPS.txt
  EOF

  tags = {
    Name = "${var.project}-airflow"
  }
}
