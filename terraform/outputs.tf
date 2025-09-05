output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_url" {
  description = "URL of the application"
  value       = "http://${aws_lb.main.dns_name}"
}

output "docdb_endpoint" {
  description = "DocumentDB cluster endpoint"
  value       = aws_docdb_cluster.main.endpoint
}

output "api_endpoints" {
  description = "Backend API endpoints"
  value = {
    optimize = "http://${aws_lb.main.dns_name}/optimize"
    status   = "http://${aws_lb.main.dns_name}/status/{uuid}"
    health   = "http://${aws_lb.main.dns_name}/health"
  }
}