from flask import Flask, request, jsonify
import boto3
import json
import uuid
import time
from datetime import datetime
from threading import Thread
app = Flask(__name__)

# AWS 클라이언트
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
pricing_client = boto3.client('pricing', region_name='us-east-1')

# 메모리 저장소
requests_store = {}

class AWSOptimizer:
    def __init__(self):
        self.pricing_cache = {}
        self.fallback_costs = {
            'EC2': {'t2.nano': 4.2, 't2.micro': 8.5, 't2.small': 17, 't2.medium': 34},
            'RDS': {'db.t3.micro': 15, 'db.t3.small': 30, 'db.t3.medium': 60},
            'S3': {'standard': 23, 'intelligent_tiering': 23},
            'Lambda': {'requests': 0.2, 'gb_seconds': 16.67}
        }
    
    def get_pricing(self, service, instance_type, region='us-east-1'):
        cache_key = f"{service}_{instance_type}_{region}"
        if cache_key in self.pricing_cache:
            return self.pricing_cache[cache_key]
        
        try:
            if service == 'EC2':
                price = self._get_ec2_price(instance_type, region)
            elif service == 'RDS':
                price = self._get_rds_price(instance_type, region)
            else:
                price = self.fallback_costs.get(service, {}).get(instance_type, 50)
            
            self.pricing_cache[cache_key] = price
            return price
        except:
            fallback = self.fallback_costs.get(service, {}).get(instance_type, 50)
            self.pricing_cache[cache_key] = fallback
            return fallback
    
    def _get_ec2_price(self, instance_type, region):
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'ap-northeast-2': 'Asia Pacific (Seoul)'
        }
        
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location_map.get(region, 'US East (N. Virginia)')},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'}
            ]
        )
        
        if response['PriceList']:
            price_data = json.loads(response['PriceList'][0])
            terms = price_data['terms']['OnDemand']
            for term_key in terms:
                price_dimensions = terms[term_key]['priceDimensions']
                for pd_key in price_dimensions:
                    hourly_price = float(price_dimensions[pd_key]['pricePerUnit']['USD'])
                    return hourly_price * 24 * 30
        
        return self.fallback_costs['EC2'].get(instance_type, 50)
    
    def _get_rds_price(self, instance_type, region):
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'ap-northeast-2': 'Asia Pacific (Seoul)'
        }
        
        response = pricing_client.get_products(
            ServiceCode='AmazonRDS',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location_map.get(region, 'US East (N. Virginia)')},
                {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'}
            ]
        )
        
        if response['PriceList']:
            price_data = json.loads(response['PriceList'][0])
            terms = price_data['terms']['OnDemand']
            for term_key in terms:
                price_dimensions = terms[term_key]['priceDimensions']
                for pd_key in price_dimensions:
                    hourly_price = float(price_dimensions[pd_key]['pricePerUnit']['USD'])
                    return hourly_price * 24 * 30
        
        return self.fallback_costs['RDS'].get(instance_type, 50)
    
    def analyze_requirements(self, prompt, budget, region='us-east-1'):
        try:
            bedrock_prompt = f"""
            다음 요구사항을 분석하여 필요한 AWS 서비스를 JSON 형태로 추천해주세요:
            
            On-Demand 인스턴스 타입을 사용하며, 필수불가결한 경우에만 Reserved 인스턴스를 고려합니다.
            비용 효율성을 최우선으로 하며, 예산 내에서 최대한의 성능을 제공합니다.
            가능한 경우 서버리스 아키텍처를 우선적으로 고려합니다.

            {prompt}
            예산: ${budget}/월
            리전: {region}
            
            응답 형식 (JSON만):
            {{
                "services": [
                    {{"name": "EC2", "type": "t2.micro", "quantity": 1, "reason": "웹서버"}},
                    {{"name": "RDS", "type": "db.t3.micro", "quantity": 1, "reason": "데이터베이스"}}
                ]
            }}
            """
            
            body = json.dumps({
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {"text": bedrock_prompt}
                        ]
                    }
                ],
                "inferenceConfig": {
                    "max_new_tokens": 1000,
                    "temperature": 0.3
                }
            })
            
            response = bedrock.invoke_model(
                modelId="amazon.nova-premier-v1:0",
                body=body,
                contentType="application/json"
            )
            
            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(content[start:end])
                return analysis['services']
        except Exception as e:
            print(f"Bedrock failed: {e}")
        
        # 폴백 분석
        services = []
        if any(word in prompt.lower() for word in ['웹', 'web', 'api']):
            services.append({"name": "EC2", "type": "t2.micro", "quantity": 1, "reason": "웹서버"})
            services.append({"name": "RDS", "type": "db.t3.micro", "quantity": 1, "reason": "데이터베이스"})
        
        return services
    
    def optimize_services(self, services, budget, region='us-east-1'):
        optimized = []
        total_cost = 0
        
        # 가격 계산 및 최적화
        for service in services:
            cost = self.get_pricing(service['name'], service['type'], region)
            
            if total_cost + cost <= budget:
                service['monthly_cost'] = round(cost, 2)
                optimized.append(service)
                total_cost += cost
            else:
                # 더 저렴한 옵션 찾기
                cheaper = self._find_cheaper_option(service['name'], budget - total_cost, region)
                if cheaper:
                    cheaper_cost = self.get_pricing(service['name'], cheaper, region)
                    service['type'] = cheaper
                    service['monthly_cost'] = round(cheaper_cost, 2)
                    service['reason'] += " (비용 최적화)"
                    optimized.append(service)
                    total_cost += cheaper_cost
        
        return optimized, round(total_cost, 2)
    
    def _find_cheaper_option(self, service_name, remaining_budget, region):
        options = {
            'EC2': ['t2.nano', 't2.micro', 't2.small'],
            'RDS': ['db.t3.micro', 'db.t3.small']
        }
        
        if service_name not in options:
            return None
        
        for option in options[service_name]:
            cost = self.get_pricing(service_name, option, region)
            if cost <= remaining_budget:
                return option
        return None

optimizer = AWSOptimizer()

def store_request(request_uuid, data):
    if request_uuid in requests_store:
        requests_store[request_uuid].update(data)
    else:
        requests_store[request_uuid] = data

def get_request(request_uuid):
    return requests_store.get(request_uuid)

def process_optimization(request_uuid, prompt, budget, region):
    try:
        # 상태 업데이트: 분석 중
        store_request(request_uuid, {
            'uuid': request_uuid,
            'status': 'analyzing',
            'prompt': prompt,
            'budget': budget,
            'region': region,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        # 1. 요구사항 분석
        services = optimizer.analyze_requirements(prompt, budget, region)
        
        store_request(request_uuid, {
            'status': 'optimizing',
            'services_analyzed': services,
            'updated_at': datetime.utcnow()
        })
        
        # 2. 서비스 최적화
        optimized_services, total_cost = optimizer.optimize_services(services, budget, region)
        
        # 3. 결과 생성
        feasible = total_cost <= budget
        
        if feasible:
            result = {
                'status': 'completed',
                'feasible': True,
                'services': optimized_services,
                'total_cost': total_cost,
                'budget': budget,
                'savings': round(budget - total_cost, 2),
                'region': region
            }
        else:
            result = {
                'status': 'completed',
                'feasible': False,
                'message': f'예산 ${budget}로는 요구사항을 충족할 수 없습니다. 최소 ${total_cost}가 필요합니다.',
                'minimum_budget': total_cost,
                'budget': budget,
                'region': region
            }
        
        result['updated_at'] = datetime.utcnow()
        store_request(request_uuid, result)
        
    except Exception as e:
        store_request(request_uuid, {
            'status': 'failed',
            'error': str(e),
            'updated_at': datetime.utcnow()
        })

@app.route('/optimize', methods=['POST'])
def create_optimization():
    data = request.json
    prompt = data.get('prompt')
    budget = float(data.get('budget', 100))
    region = data.get('region', 'us-east-1')
    
    request_uuid = str(uuid.uuid4())
    
    # 비동기 처리 시작
    thread = Thread(target=process_optimization, args=(request_uuid, prompt, budget, region))
    thread.start()
    
    return jsonify({'uuid': request_uuid, 'status': 'processing'})

@app.route('/status/<request_uuid>')
def get_status(request_uuid):
    result = get_request(request_uuid)
    
    if not result:
        return jsonify({'status': 'not_found'}), 404
    
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)