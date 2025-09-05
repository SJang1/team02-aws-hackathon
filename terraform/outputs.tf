output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_url" {
  description = "URL of the application"
  value       = "http://${aws_lb.main.dns_name}"
}