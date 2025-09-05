terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# Public Subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

# Private Subnet
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = {
    Name = "${var.project_name}-private-subnet"
  }
}

# Additional Private Subnet for RDS (Multi-AZ)
resource "aws_subnet" "private_db" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = {
    Name = "${var.project_name}-private-db-subnet"
  }
}

# Route Table for Public Subnet
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security Group for Web Server
resource "aws_security_group" "web" {
  name_prefix = "${var.project_name}-web-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-web-sg"
  }
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}

# IAM Role for EC2
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

# IAM Policy for Bedrock, Pricing and RDS
resource "aws_iam_policy" "bedrock_pricing_rds_policy" {
  name        = "${var.project_name}-bedrock-pricing-rds-policy"
  description = "Policy for Bedrock, Pricing API and RDS access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "pricing:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:*:*:parameter/team02-hackathon/*"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-bedrock-pricing-rds-policy"
  }
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "bedrock_pricing_rds_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.bedrock_pricing_rds_policy.arn
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private.id, aws_subnet.private_db.id]

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "mysql"
  engine_version = "8.0"
  instance_class = "db.t3.micro"
  
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  storage_encrypted     = true
  
  db_name  = "clops"
  username = "admin"
  password = random_password.db_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  skip_final_snapshot = true
  deletion_protection = false
  
  tags = {
    Name = "${var.project_name}-database"
  }
}

# Random password for RDS
resource "random_password" "db_password" {
  length  = 16
  special = true
}

# Store RDS password in AWS Systems Manager Parameter Store
resource "aws_ssm_parameter" "rds_password" {
  name  = "/team02-hackathon/rds/password"
  type  = "SecureString"
  value = random_password.db_password.result

  tags = {
    Name = "${var.project_name}-rds-password"
  }
}

# Instance Profile
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name

  tags = {
    Name = "${var.project_name}-ec2-profile"
  }
}

# EC2 Instance
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name              = aws_key_pair.main.key_name
  vpc_security_group_ids = [aws_security_group.web.id]
  subnet_id             = aws_subnet.public.id
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
              #!/bin/bash
              
              # Install nginx and openssl
              yum update -y
              amazon-linux-extras install nginx1 -y
              yum install -y openssl nginx
              
              # Create SSL certificate directory
              mkdir -p /etc/nginx/ssl
              
              # Generate self-signed SSL certificate
              openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout /etc/nginx/ssl/nginx.key \
                -out /etc/nginx/ssl/nginx.crt \
                -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
              
              # Configure nginx reverse proxy with HTTPS
              cat > /etc/nginx/nginx.conf << 'NGINX_EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

include /usr/share/nginx/modules/*.conf;

events {
    worker_connections 1024;
}

http {
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    sendfile            on;
    tcp_nopush          on;
    tcp_nodelay         on;
    keepalive_timeout   65;
    types_hash_max_size 4096;

    include             /etc/nginx/mime.types;
    default_type        application/octet-stream;

    # HTTP server
    server {
        listen       80 default_server;
        listen       [::]:80 default_server;
        server_name  _;

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # HTTPS server
    server {
        listen       443 ssl http2 default_server;
        listen       [::]:443 ssl http2 default_server;
        server_name  _;

        ssl_certificate /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;
        ssl_session_cache shared:SSL:1m;
        ssl_session_timeout 10m;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
NGINX_EOF
              
              # Start nginx
              systemctl start nginx
              systemctl enable nginx
              
              # Install git and clone repository
              yum install -y git
              cd /home/ec2-user
              
              # Clone the repository
              git clone ${var.git_repo_url} repo || \
              echo "Repository clone failed, creating placeholder files"
              
              # Set RDS password as environment variable for the application
              echo "export RDS_USERNAME=${aws_db_instance.main.username}" >> /home/ec2-user/.bashrc
              echo "export RDS_PASSWORD='${random_password.db_password.result}'" >> /home/ec2-user/.bashrc
              export RDS_PASSWORD='${random_password.db_password.result}'
              
              # Install Python and dependencies
              yum install -y python3 python3-pip
              
              # If clone succeeded, copy files to home directory
              if [ -d "repo" ]; then
                cp -r repo/* .
                chmod +x start_servers.sh
                chmod +x test_rds_connection.py 2>/dev/null || true
                
                # Start servers with RDS password
                RDS_USERNAME='${aws_db_instance.main.username}' RDS_PASSWORD='${random_password.db_password.result}' bash ./start_servers.sh &
              else
                # Fallback: create simple test server
                pip3 install flask pymysql cryptography boto3
                cat > test_app.py << 'PYTHON_EOF'
from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello():
    return '<h1>ClOps RDS Ready</h1><p>RDS integration configured</p>'
@app.route('/health')
def health():
    return {'status': 'healthy', 'database': 'RDS MySQL'}
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
PYTHON_EOF
                nohup python3 test_app.py > app.log 2>&1 &
              fi
              
              # Wait for RDS to be ready
              echo "Waiting for RDS to be ready..."
              sleep 60
              
              # Test RDS connection
              yum install -y mysql
              for i in {1..10}; do
                if mysql -h ${aws_db_instance.main.endpoint} -u ${aws_db_instance.main.username} -p${random_password.db_password.result} -e "SELECT 1;" 2>/dev/null; then
                  echo "RDS is ready!"
                  break
                else
                  echo "RDS not ready, waiting... ($i/10)"
                  sleep 30
                fi
              done
              EOF

  tags = {
    Name = "${var.project_name}-web-server"
  }
}

# S3 Bucket
resource "aws_s3_bucket" "main" {
  bucket = "${var.project_name}-bucket-${random_string.bucket_suffix.result}"

  tags = {
    Name = "${var.project_name}-bucket"
  }
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Key Pair
resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = var.public_key != "" ? var.public_key : tls_private_key.main[0].public_key_openssh

  tags = {
    Name = "${var.project_name}-key"
  }
}

# Generate private key if public_key is not provided
resource "tls_private_key" "main" {
  count     = var.public_key == "" ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

# Save private key to local file
resource "local_file" "private_key" {
  count    = var.public_key == "" ? 1 : 0
  content  = tls_private_key.main[0].private_key_pem
  filename = "${var.project_name}-key.pem"
  file_permission = "0400"
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}