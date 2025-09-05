from flask import Flask, request, jsonify
import boto3
import json
import uuid
import time
from datetime import datetime
import os
from threading import Thread

app = Flask(__name__)

# AWS 클라이언트 초기화
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
pricing = boto3.client('pricing', region_name='us-east-1')

# 메모리 저장소 (실제 환경에서는 DynamoDB 사용)
results_store = {}

class AWSServiceEstimator:
    def __init__(self):
        self.service_costs = {
            'EC2': {'t2.micro': 8.5, 't2.small': 17, 't2.medium': 34, 't3.medium': 38},
            'RDS': {'db.t3.micro': 15, 'db.t3.small': 30, 'db.t3.medium': 60},
            'S3': {'standard': 0.023, 'ia': 0.0125},
            'CloudFront': {'requests': 0.0075, 'data': 0.085},
            'Lambda': {'requests': 0.0000002, 'duration': 0.0000166667},
            'API_Gateway': {'requests': 3.5}
        }
    
    def analyze_requirements(self, prompt, budget):
        """Bedrock을 통한 요구사항 분석"""
        try:
            bedrock_prompt = f"""
            다음 요구사항을 분석하여 필요한 AWS 서비스를 JSON 형태로 추천해주세요:
            
            {prompt}
            
            응답 형식:
            {{
                "services": [
                    {{"name": "EC2", "type": "t2.micro", "quantity": 1, "reason": "웹서버용"}},
                    {{"name": "RDS", "type": "db.t3.micro", "quantity": 1, "reason": "데이터베이스"}}
                ],
                "estimated_cost": 50,
                "feasible": true
            }}
            """
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-sonnet-20240229-v1:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 1000,
                    'messages': [{'role': 'user', 'content': bedrock_prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            
            # JSON 추출
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(content[start:end])
            
        except Exception as e:
            print(f"Bedrock 오류: {e}")
            
        # 폴백 로직
        return self._fallback_analysis(prompt, budget)
    
    def _fallback_analysis(self, prompt, budget):
        """Bedrock 실패 시 폴백 분석"""
        services = []
        total_cost = 0
        
        # 기본 웹서비스 구성
        if any(word in prompt.lower() for word in ['웹', 'web', 'api']):
            services.append({"name": "EC2", "type": "t2.micro", "quantity": 1, "reason": "웹서버"})
            total_cost += self.service_costs['EC2']['t2.micro']
            
            services.append({"name": "RDS", "type": "db.t3.micro", "quantity": 1, "reason": "데이터베이스"})
            total_cost += self.service_costs['RDS']['db.t3.micro']
        
        return {
            "services": services,
            "estimated_cost": total_cost,
            "feasible": total_cost <= float(budget)
        }
    
    def optimize_services(self, services, budget):
        """서비스 최적화 및 통합"""
        optimized = []
        total_cost = 0
        
        for service in services:
            service_name = service['name']
            service_type = service['type']
            
            if service_name in self.service_costs and service_type in self.service_costs[service_name]:
                cost = self.service_costs[service_name][service_type]
                if total_cost + cost <= float(budget):
                    optimized.append(service)
                    total_cost += cost
                else:
                    # 더 저렴한 옵션 찾기
                    cheaper_option = self._find_cheaper_option(service_name, float(budget) - total_cost)
                    if cheaper_option:
                        optimized.append({
                            **service,
                            "type": cheaper_option,
                            "reason": f"{service['reason']} (비용 최적화)"
                        })
                        total_cost += self.service_costs[service_name][cheaper_option]
        
        return optimized, total_cost
    
    def _find_cheaper_option(self, service_name, remaining_budget):
        """더 저렴한 서비스 옵션 찾기"""
        if service_name not in self.service_costs:
            return None
            
        for option, cost in sorted(self.service_costs[service_name].items(), key=lambda x: x[1]):
            if cost <= remaining_budget:
                return option
        return None

estimator = AWSServiceEstimator()

def process_request(request_uuid, prompt, budget):
    """비동기 요청 처리"""
    try:
        results_store[request_uuid] = {'status': 'processing'}
        
        # 1. Bedrock 분석
        analysis = estimator.analyze_requirements(prompt, budget)
        
        # 2. 서비스 최적화
        if analysis['feasible']:
            optimized_services, final_cost = estimator.optimize_services(analysis['services'], budget)
            
            result = {
                'status': 'completed',
                'feasible': True,
                'services': optimized_services,
                'total_cost': final_cost,
                'budget': float(budget),
                'savings': float(budget) - final_cost
            }
        else:
            # 3. 서비스 통합 시도
            optimized_services, final_cost = estimator.optimize_services(analysis['services'], budget)
            
            if final_cost <= float(budget):
                result = {
                    'status': 'completed',
                    'feasible': True,
                    'services': optimized_services,
                    'total_cost': final_cost,
                    'budget': float(budget),
                    'note': '일부 서비스가 최적화되었습니다.'
                }
            else:
                result = {
                    'status': 'completed',
                    'feasible': False,
                    'message': f'예산 ${budget}로는 요구사항을 충족할 수 없습니다. 최소 ${final_cost}가 필요합니다.',
                    'minimum_budget': final_cost
                }
        
        results_store[request_uuid] = result
        
    except Exception as e:
        results_store[request_uuid] = {
            'status': 'failed',
            'error': str(e)
        }

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    request_uuid = data.get('uuid')
    prompt = data.get('prompt')
    budget = data.get('budget')
    
    # 비동기 처리 시작
    thread = Thread(target=process_request, args=(request_uuid, prompt, budget))
    thread.start()
    
    return jsonify({'uuid': request_uuid, 'status': 'processing'})

@app.route('/result/<request_uuid>')
def get_result(request_uuid):
    result = results_store.get(request_uuid, {'status': 'not_found'})
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)