variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "EC2 Key Pair name"
  type        = string
}

variable "backend_repo" {
  description = "Backend repository URL"
  type        = string
  default     = "https://github.com/your-repo/backend.git"
}