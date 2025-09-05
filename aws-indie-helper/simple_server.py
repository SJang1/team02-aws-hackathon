#!/usr/bin/env python3
"""
Simple HTTP server for AWS Indie Helper
No external dependencies required
"""

import http.server
import socketserver
import json
import urllib.parse
from typing import Dict, List

class IndieHelperHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/recommend':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                request_data = json.loads(post_data.decode('utf-8'))
                recommendations = self.get_recommendations(request_data)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response = json.dumps(recommendations, indent=2)
                self.wfile.write(response.encode('utf-8'))
                
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def get_recommendations(self, request: Dict) -> Dict:
        project_type = request.get('project_type', 'web_service')
        users = request.get('expected_users', 100)
        budget = request.get('budget', 100.0)
        
        if project_type == "web_service":
            recommendations = [
                {
                    "service_name": "EC2",
                    "instance_type": "t3.micro" if users < 1000 else "t3.small",
                    "monthly_cost": 8.5 if users < 1000 else 17.0,
                    "description": "웹 서버 호스팅"
                },
                {
                    "service_name": "RDS",
                    "instance_type": "db.t3.micro",
                    "monthly_cost": 15.0,
                    "description": "MySQL 데이터베이스"
                },
                {
                    "service_name": "S3",
                    "instance_type": "Standard",
                    "monthly_cost": 5.0,
                    "description": "정적 파일 저장소"
                },
                {
                    "service_name": "CloudFront",
                    "instance_type": "Standard",
                    "monthly_cost": 10.0,
                    "description": "CDN 서비스"
                }
            ]
        else:  # game
            recommendations = [
                {
                    "service_name": "EC2",
                    "instance_type": "t3.small",
                    "monthly_cost": 17.0,
                    "description": "게임 서버"
                },
                {
                    "service_name": "DynamoDB",
                    "instance_type": "On-Demand",
                    "monthly_cost": 12.0,
                    "description": "게임 데이터 저장"
                },
                {
                    "service_name": "S3",
                    "instance_type": "Standard",
                    "monthly_cost": 8.0,
                    "description": "게임 에셋 저장"
                },
                {
                    "service_name": "GameLift",
                    "instance_type": "c5.large",
                    "monthly_cost": 50.0,
                    "description": "멀티플레이어 게임 호스팅"
                }
            ]
        
        total_cost = sum(rec["monthly_cost"] for rec in recommendations)
        
        terraform_config = self.generate_terraform(recommendations)
        
        return {
            "recommendations": recommendations,
            "total_monthly_cost": total_cost,
            "terraform_config": terraform_config
        }
    
    def generate_terraform(self, recommendations: List[Dict]) -> str:
        config = 'provider "aws" {\n  region = "us-east-1"\n}\n\n'
        
        for rec in recommendations:
            if rec["service_name"] == "EC2":
                config += f'''resource "aws_instance" "main" {{
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "{rec['instance_type']}"
  
  tags = {{
    Name = "indie-helper-server"
  }}
}}

'''
            elif rec["service_name"] == "RDS":
                config += '''resource "aws_db_instance" "main" {
  identifier = "indie-helper-db"
  engine     = "mysql"
  engine_version = "8.0"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  
  db_name  = "indiehelper"
  username = "admin"
  password = "changeme123!"
  
  skip_final_snapshot = true
}

'''
        
        return config

if __name__ == "__main__":
    PORT = 8000
    with socketserver.TCPServer(("", PORT), IndieHelperHandler) as httpd:
        print(f"🔧 백엔드 API 서버 시작: http://localhost:{PORT}")
        print("종료하려면 Ctrl+C를 누르세요")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버 종료")
            httpd.shutdown()