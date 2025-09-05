from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import boto3

app = FastAPI(title="AWS Indie Helper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProjectRequest(BaseModel):
    project_type: str  # "web_service" or "game"
    expected_users: int
    budget: float
    region: str = "us-east-1"

class ServiceRecommendation(BaseModel):
    service_name: str
    instance_type: str
    monthly_cost: float
    description: str

@app.post("/api/recommend")
async def recommend_services(request: ProjectRequest) -> Dict:
    recommendations = get_service_recommendations(
        request.project_type, 
        request.expected_users, 
        request.budget
    )
    
    total_cost = sum(rec["monthly_cost"] for rec in recommendations)
    
    return {
        "recommendations": recommendations,
        "total_monthly_cost": total_cost,
        "terraform_config": generate_terraform_config(recommendations)
    }

def get_service_recommendations(project_type: str, users: int, budget: float) -> List[Dict]:
    if project_type == "web_service":
        return [
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
    
    elif project_type == "game":
        return [
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
    
    return []

def generate_terraform_config(recommendations: List[Dict]) -> str:
    config = """
provider "aws" {
  region = "us-east-1"
}

"""
    
    for rec in recommendations:
        if rec["service_name"] == "EC2":
            config += f"""
resource "aws_instance" "main" {{
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "{rec['instance_type']}"
  
  tags = {{
    Name = "indie-helper-server"
  }}
}}
"""
        elif rec["service_name"] == "RDS":
            config += """
resource "aws_db_instance" "main" {
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
"""
    
    return config

@app.get("/")
async def root():
    return {"message": "AWS Indie Helper API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)