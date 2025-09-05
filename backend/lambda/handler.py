import json
import boto3
import os
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS 서비스 추천 Lambda 함수
    """
    try:
        # CORS 헤더
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
        
        # OPTIONS 요청 처리
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': ''
            }
        
        # 요청 데이터 파싱
        body = json.loads(event.get('body', '{}'))
        description = body.get('description', '')
        budget = body.get('budget', 0)
        
        if not description or budget <= 0:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '유효하지 않은 입력입니다.'})
            }
        
        # AI 추천 생성 (Phase 2에서 Bedrock 연동)
        recommendation = generate_recommendation(description, budget)
        
        # DynamoDB에 저장 (Phase 1에서는 생략)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(recommendation)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def generate_recommendation(description: str, budget: int) -> Dict[str, Any]:
    """
    임시 추천 로직 (Phase 2에서 Bedrock으로 교체)
    """
    # 기본 서비스 매핑
    services = ['EC2', 'RDS', 'S3']
    
    if 'web' in description.lower() or '웹' in description:
        services.extend(['CloudFront', 'Route 53'])
    
    if 'api' in description.lower() or 'API' in description:
        services.extend(['API Gateway', 'Lambda'])
    
    if 'database' in description.lower() or '데이터베이스' in description:
        services.append('DynamoDB')
    
    # 중복 제거
    services = list(set(services))
    
    return {
        'services': services,
        'architecture': f"""추천 아키텍처:
- {', '.join(services[:3])}를 중심으로 한 구성
- 예산 ${budget}에 맞춘 최적화된 설계
- 확장 가능한 서버리스 아키텍처 고려""",
        'estimatedCost': min(budget * 0.8, 1000)
    }