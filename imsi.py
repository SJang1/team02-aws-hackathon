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
    
    def analyze_requirements(self, service_type, users, performance, additional_info, budget, region='us-east-1'):
        try:
            bedrock_prompt = f"""
            AWS 서비스 추천 요청:
            - 서비스 유형: {service_type}
            - 예상 사용자 수: {users}
            - 성능 요구사항: {performance}
            - 추가 요구사항: {additional_info}
            - 예산: ${budget}/월
            - 리전: {region}
            
            On-Demand 인스턴스 타입을 사용하며, 비용 효율성을 최우선으로 합니다.
            
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
                    "max_new_tokens": 800000,
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
        return self._fallback_analysis(service_type, users, performance, additional_info)
    
    def _fallback_analysis(self, service_type, users, performance, additional_info):
        services = []
        
        # 사용자 규모 정규화
        if users in ['소규모', '1-100명', '100명 이하']:
            user_scale = 'small'
        elif users in ['중간규모', '100-1,000명', '1000명 이하']:
            user_scale = 'medium'
        elif users in ['대규모', '1,000-10,000명', '10000명 이하']:
            user_scale = 'large'
        elif users in ['엔터프라이즈', '10,000명+', '10000명 이상']:
            user_scale = 'enterprise'
        else:
            # 기타 옵션으로 직접 입력한 경우
            if any(word in users.lower() for word in ['100', '소규모', 'small']):
                user_scale = 'small'
            elif any(word in users.lower() for word in ['1000', '중간', 'medium']):
                user_scale = 'medium'
            elif any(word in users.lower() for word in ['10000', '대규모', 'large']):
                user_scale = 'large'
            else:
                user_scale = 'medium'  # 기본값
        
        # 서비스 유형 처리 (기타 옵션 포함)
        if service_type in ['웹사이트', 'API'] or any(word in service_type.lower() for word in ['web', 'api', '웹', '사이트']):
            if user_scale == 'small':
                ec2_type = 't2.micro'
            elif user_scale == 'medium':
                ec2_type = 't2.small'
            elif user_scale == 'large':
                ec2_type = 't2.medium'
            else:
                ec2_type = 't3.medium'
            
            if performance in ['고성능', '최고성능'] and ec2_type == 't2.micro':
                ec2_type = 't2.small'
            
            services.append({"name": "EC2", "type": ec2_type, "quantity": 1, "reason": "웹서버/API서버"})
            
            if '데이터베이스' in additional_info or service_type == '웹사이트':
                rds_type = 'db.t3.micro' if user_scale == 'small' else 'db.t3.small'
                services.append({"name": "RDS", "type": rds_type, "quantity": 1, "reason": "데이터베이스"})
        
        elif service_type == '데이터베이스' or 'database' in service_type.lower() or 'db' in service_type.lower():
            if user_scale == 'small':
                rds_type = 'db.t3.micro'
            elif user_scale == 'medium':
                rds_type = 'db.t3.small'
            else:
                rds_type = 'db.t3.medium'
            services.append({"name": "RDS", "type": rds_type, "quantity": 1, "reason": "메인 데이터베이스"})
        
        elif service_type == '머신러닝' or any(word in service_type.lower() for word in ['ml', 'ai', 'machine', 'learning']):
            services.append({"name": "EC2", "type": 't3.medium', "quantity": 1, "reason": "ML 워크로드"})
            services.append({"name": "S3", "type": "standard", "quantity": 1, "reason": "데이터 저장소"})
        
        elif service_type == '스토리지' or any(word in service_type.lower() for word in ['storage', 'file', '파일', '저장']):
            services.append({"name": "S3", "type": "standard", "quantity": 1, "reason": "파일 저장소"})
        
        elif service_type == '분석' or any(word in service_type.lower() for word in ['analytics', 'analysis', '분석']):
            services.append({"name": "EC2", "type": 't3.medium', "quantity": 1, "reason": "데이터 분석 서버"})
            services.append({"name": "S3", "type": "standard", "quantity": 1, "reason": "데이터 레이크"})
        
        else:
            # 기타 서비스 유형에 대한 기본 처리
            services.append({"name": "EC2", "type": 't2.small', "quantity": 1, "reason": f"{service_type} 서버"})
        
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

def process_optimization(request_uuid, service_type, users, performance, additional_info, budget, region):
    try:
        store_request(request_uuid, {
            'uuid': request_uuid,
            'status': 'analyzing',
            'service_type': service_type,
            'users': users,
            'performance': performance,
            'additional_info': additional_info,
            'budget': budget,
            'region': region,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        services = optimizer.analyze_requirements(service_type, users, performance, additional_info, budget, region)
        
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
    
    service_type = data.get('service_type', '')
    users = data.get('users', '소규모')
    performance = data.get('performance', '기본')
    additional_info = data.get('additional_info', '')
    budget = float(data.get('budget', 100))
    region = data.get('region', 'us-east-1')
    
    request_uuid = str(uuid.uuid4())
    
    thread = Thread(target=process_optimization, args=(request_uuid, service_type, users, performance, additional_info, budget, region))
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