from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pricing_service import AWSPricingService

app = FastAPI(title="AWS Service Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# AWS 클라이언트 초기화
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
pricing_service = AWSPricingService()

class ServiceRequest(BaseModel):
    description: str
    budget: float

@app.post("/api/recommend")
async def recommend_services(request: ServiceRequest) -> Dict:
    try:
        # 1. AWS Pricing API에서 실시간 가격 정보 수집
        pricing_data = await collect_pricing_data()
        
        # 2. 가격 정보와 함께 Bedrock에 추천 요청
        bedrock_response = await generate_bedrock_recommendation_with_pricing(
            request.description, request.budget, pricing_data
        )
        
        # 3. Bedrock 추천 결과를 바탕으로 정확한 비용 계산
        final_services = await calculate_final_costs(
            bedrock_response['services'], request.budget
        )
        
        result = {
            "services": final_services,
            "architecture": bedrock_response.get('architecture', ''),
            "total_cost": sum(s['monthly_cost'] for s in final_services),
            "budget_utilization": min(100, (sum(s['monthly_cost'] for s in final_services) / request.budget) * 100),
            "cost_breakdown": generate_cost_breakdown(final_services)
        }
        
        # 4. DynamoDB에 저장
        await save_recommendation(request.description, request.budget, result)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def collect_pricing_data() -> Dict:
    """AWS Pricing API에서 실시간 가격 정보 수집"""
    common_services = ['EC2', 'RDS', 'S3', 'CloudFront', 'Lambda', 'DynamoDB', 'API Gateway']
    pricing_data = pricing_service.get_service_estimates(common_services)
    
    # 인스턴스 타입별 상세 가격 정보
    ec2_prices = {
        't3.micro': pricing_service.get_ec2_pricing('t3.micro'),
        't3.small': pricing_service.get_ec2_pricing('t3.small'),
        't3.medium': pricing_service.get_ec2_pricing('t3.medium')
    }
    
    rds_prices = {
        'db.t3.micro': pricing_service.get_rds_pricing('db.t3.micro'),
        'db.t3.small': pricing_service.get_rds_pricing('db.t3.small')
    }
    
    return {
        'services': pricing_data,
        'ec2_instances': {k: v for k, v in ec2_prices.items() if v},
        'rds_instances': {k: v for k, v in rds_prices.items() if v}
    }

async def generate_bedrock_recommendation_with_pricing(description: str, budget: float, pricing_data: Dict) -> Dict:
    """가격 정보를 포함하여 Bedrock에 추천 요청"""
    prompt = f"""
사용자 요구사항: {description}
예산: ${budget}/월

현재 AWS 서비스 가격 정보:
{json.dumps(pricing_data, indent=2, ensure_ascii=False)}

위 가격 정보를 참고하여 예산 내에서 최적의 AWS 서비스 조합을 추천해주세요.
응답은 반드시 다음 JSON 형태로 해주세요:
{{
  "services": [
    {{
      "name": "EC2",
      "instance_type": "t3.micro",
      "reason": "선택 이유"
    }}
  ],
  "architecture": "상세한 아키텍처 설명과 구성 방법",
  "cost_optimization_tips": "비용 최적화 팁"
}}
"""
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2000,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(content[start:end])
            
    except Exception as e:
        print(f"Bedrock error: {e}")
    
    # Fallback
    return {
        'services': [
            {'name': 'EC2', 'instance_type': 't3.micro', 'reason': '기본 웹 서버'},
            {'name': 'RDS', 'instance_type': 'db.t3.micro', 'reason': '데이터베이스'},
            {'name': 'S3', 'instance_type': 'Standard', 'reason': '파일 저장소'}
        ],
        'architecture': f'예산 ${budget}에 맞춘 기본 웹 서비스 구성'
    }

async def calculate_final_costs(services: List[Dict], budget: float) -> List[Dict]:
    """Bedrock 추천 결과를 바탕으로 정확한 비용 계산"""
    final_services = []
    
    for service in services:
        service_name = service['name']
        instance_type = service.get('instance_type', '')
        
        # 실시간 가격 조회
        if service_name == 'EC2':
            actual_cost = pricing_service.get_ec2_pricing(instance_type)
        elif service_name == 'RDS':
            actual_cost = pricing_service.get_rds_pricing(instance_type)
        else:
            # 기타 서비스는 기본 가격 사용
            service_estimates = pricing_service.get_service_estimates([service_name])
            actual_cost = service_estimates.get(service_name)
        
        if actual_cost:
            final_services.append({
                'service_name': service_name,
                'instance_type': instance_type,
                'monthly_cost': actual_cost,
                'description': get_service_description(service_name),
                'reason': service.get('reason', ''),
                'cost_per_hour': actual_cost / (24 * 30) if actual_cost else 0
            })
    
    # 예산 초과 시 최적화
    total_cost = sum(s['monthly_cost'] for s in final_services)
    if total_cost > budget:
        final_services = optimize_for_budget_advanced(final_services, budget)
    
    return final_services

def generate_cost_breakdown(services: List[Dict]) -> Dict:
    """비용 분석 정보 생성"""
    total_cost = sum(s['monthly_cost'] for s in services)
    
    breakdown = {
        'total_monthly': total_cost,
        'total_yearly': total_cost * 12,
        'by_service': {},
        'cost_distribution': {}
    }
    
    for service in services:
        service_name = service['service_name']
        cost = service['monthly_cost']
        
        breakdown['by_service'][service_name] = {
            'monthly': cost,
            'yearly': cost * 12,
            'percentage': (cost / total_cost * 100) if total_cost > 0 else 0
        }
    
    return breakdown

def optimize_for_budget_advanced(services: List[Dict], budget: float) -> List[Dict]:
    """고급 예산 최적화 로직"""
    # 필수 서비스 우선순위 (EC2, RDS 등)
    priority_services = ['EC2', 'RDS']
    optional_services = ['S3', 'CloudFront', 'Lambda', 'DynamoDB']
    
    optimized = []
    current_cost = 0
    
    # 1. 필수 서비스 먼저 추가
    for service in services:
        if service['service_name'] in priority_services:
            if current_cost + service['monthly_cost'] <= budget:
                optimized.append(service)
                current_cost += service['monthly_cost']
    
    # 2. 선택적 서비스 비용 효율성 순으로 추가
    optional_list = [s for s in services if s['service_name'] in optional_services]
    optional_list.sort(key=lambda x: x['monthly_cost'])
    
    for service in optional_list:
        if current_cost + service['monthly_cost'] <= budget:
            optimized.append(service)
            current_cost += service['monthly_cost']
    
    return optimized

def get_service_description(service: str) -> str:
    descriptions = {
        'EC2': '가상 서버 인스턴스',
        'RDS': '관리형 데이터베이스',
        'S3': '객체 스토리지',
        'CloudFront': 'CDN 서비스',
        'Lambda': '서버리스 컴퓨팅',
        'DynamoDB': 'NoSQL 데이터베이스',
        'API Gateway': 'API 관리 서비스'
    }
    return descriptions.get(service, '클라우드 서비스')



async def save_recommendation(description: str, budget: float, result: Dict):
    try:
        table = dynamodb.Table('aws-recommendations')
        table.put_item(
            Item={
                'id': str(uuid.uuid4()),
                'description': description,
                'budget': budget,
                'recommendation': result,
                'timestamp': datetime.now().isoformat()
            }
        )
    except Exception:
        pass

@app.get("/")
async def root():
    return {"message": "AWS Service Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)