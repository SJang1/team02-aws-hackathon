import json
import boto3
import os
import uuid
from datetime import datetime
from typing import Dict, Any

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'dev-recommendations'))

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    try:
        body = json.loads(event.get('body', '{}'))
        description = body.get('description', '')
        budget = body.get('budget', 0)
        
        if not description or budget <= 0:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '유효하지 않은 입력입니다.'})
            }
        
        # Bedrock으로 추천 생성
        recommendation = generate_bedrock_recommendation(description, budget)
        
        # DynamoDB에 저장
        save_recommendation(description, budget, recommendation)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(recommendation, ensure_ascii=False)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def generate_bedrock_recommendation(description: str, budget: int) -> Dict[str, Any]:
    prompt = f"""
사용자 요구사항: {description}
예산: ${budget}

위 요구사항에 맞는 AWS 서비스 추천과 아키텍처를 JSON 형태로 제공해주세요:
{{
  "services": ["서비스1", "서비스2"],
  "architecture": "아키텍처 설명",
  "estimatedCost": 예상비용숫자
}}
"""
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        
        # JSON 추출
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(content[start:end])
            
    except Exception:
        pass
    
    # Fallback
    return {
        'services': ['EC2', 'RDS', 'S3'],
        'architecture': f'예산 ${budget}에 맞춘 기본 웹 서비스 구성',
        'estimatedCost': min(budget * 0.8, 1000)
    }

def save_recommendation(description: str, budget: int, recommendation: Dict[str, Any]):
    try:
        table.put_item(
            Item={
                'id': str(uuid.uuid4()),
                'description': description,
                'budget': budget,
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat()
            }
        )
    except Exception:
        pass