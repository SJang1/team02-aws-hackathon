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
            'EC2': {'t2.nano': 4.2, 't2.micro': 8.5, 't2.small': 17, 't2.medium': 34, 't3.medium': 38, 't3.large': 76},
            'RDS': {'db.t3.micro': 15, 'db.t3.small': 30, 'db.t3.medium': 60, 'db.t3.large': 120},
            'ALB': {'application': 22},
            'S3': {'standard': 23},
            'SageMaker': {'ml.t3.medium': 45, 'ml.t3.large': 90},
            'Lambda': {'requests': 0.2}
        }
    
    def get_pricing(self, service, instance_type, region='us-east-1'):
        cache_key = f"{service}_{instance_type}_{region}"
        if cache_key in self.pricing_cache:
            return self.pricing_cache[cache_key]
        
        try:
            price = self._get_aws_service_price(service, instance_type, region)
            self.pricing_cache[cache_key] = price
            print(f"Price fetched: {service} {instance_type} = ${price}/month")
            return price
        except Exception as e:
            print(f"Pricing API failed for {service} {instance_type}: {e}")
            return None
    
    def _get_aws_service_price(self, service, instance_type, region):
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'ap-northeast-2': 'Asia Pacific (Seoul)'
        }
        
        service_configs = {
            'EC2': {
                'ServiceCode': 'AmazonEC2',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'}
                ]
            },
            'RDS': {
                'ServiceCode': 'AmazonRDS',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'}
                ]
            }
        }
        
        if service not in service_configs:
            return self.fallback_costs.get(service, {}).get(instance_type, 50)
        
        config = service_configs[service]
        filters = config['filters'].copy()
        filters.append({
            'Type': 'TERM_MATCH', 
            'Field': 'location', 
            'Value': location_map.get(region, 'US East (N. Virginia)')
        })
        
        response = pricing_client.get_products(
            ServiceCode=config['ServiceCode'],
            Filters=filters
        )
        
        if response['PriceList']:
            price_data = json.loads(response['PriceList'][0])
            if 'terms' in price_data and 'OnDemand' in price_data['terms']:
                terms = price_data['terms']['OnDemand']
                for term_key in terms:
                    price_dimensions = terms[term_key]['priceDimensions']
                    for pd_key in price_dimensions:
                        price_per_unit = price_dimensions[pd_key]['pricePerUnit']['USD']
                        if price_per_unit and float(price_per_unit) > 0:
                            hourly_price = float(price_per_unit)
                            return hourly_price * 24 * 30
        
        return None
    
    def step1_get_required_services(self, service_type, users, performance, additional_info, region='us-east-1'):
        """1단계: AI를 통해 필요한 서비스 목록 추출"""
        try:
            bedrock_prompt = f"""
            AWS 서비스 추천 요청:
            - 서비스 유형: {service_type}
            - 예상 사용자 수: {users}
            - 성능 요구사항: {performance}
            - 추가 요구사항: {additional_info}
            - 리전: {region}
            
            예산은 고려하지 말고, 이상적인 아키텍처를 위해 필요한 AWS 서비스들을 나열해주세요.
            인스턴스 타입은 지정하지 말고 서비스 이름만 나열해주세요.
            오토스케일링 등도 전부 고려 해 주세요.
            
            예시 응답:
            {{
                "services": [
                    {{"name": "EC2", "reason": "웹서버 호스팅"}},
                    {{"name": "RDS", "reason": "데이터베이스 저장"}},
                    {{"name": "ALB", "reason": "로드 밸런싱"}}
                ]
            }}
            """
            
            body = json.dumps({
                "messages": [{
                    "role": "user", 
                    "content": [{"text": bedrock_prompt}]
                }],
                "inferenceConfig": {
                    "max_new_tokens": 32768,
                    "temperature": 0.3
                }
            })
            
            response = bedrock.invoke_model(
                modelId="us.amazon.nova-premier-v1:0",
                body=body,
                contentType="application/json"
            )

            print(response['body'].read().decode('utf-8'))
            
            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(content[start:end])
                return analysis['services']
        except Exception as e:
            print(f"Step 1 Bedrock failed: {e}")
        
        return self._fallback_services(service_type)
    
    def step2_get_service_prices(self, services, region='us-east-1'):
        """2단계: 각 서비스의 다양한 옵션별 가격 조회"""
        service_options = {
            'EC2': [
                't2.nano', 't2.micro', 't2.small', 't2.medium', 't2.large', 't2.xlarge',
                't3.nano', 't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
                't3a.nano', 't3a.micro', 't3a.small', 't3a.medium', 't3a.large', 't3a.xlarge',
                'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge',
                'm6i.large', 'm6i.xlarge', 'm6i.2xlarge',
                'c5.large', 'c5.xlarge', 'c5.2xlarge',
                'r5.large', 'r5.xlarge', 'r5.2xlarge'
            ],
            'RDS': [
                'db.t3.micro', 'db.t3.small', 'db.t3.medium', 'db.t3.large', 'db.t3.xlarge', 'db.t3.2xlarge',
                'db.t4g.micro', 'db.t4g.small', 'db.t4g.medium', 'db.t4g.large',
                'db.m5.large', 'db.m5.xlarge', 'db.m5.2xlarge', 'db.m5.4xlarge',
                'db.m6i.large', 'db.m6i.xlarge', 'db.m6i.2xlarge',
                'db.r5.large', 'db.r5.xlarge', 'db.r5.2xlarge'
            ],
            'ALB': ['application'],
            'NLB': ['network'],
            'S3': ['standard', 'intelligent_tiering', 'standard_ia', 'onezone_ia', 'glacier', 'deep_archive'],
            'SageMaker': [
                'ml.t3.medium', 'ml.t3.large', 'ml.t3.xlarge', 'ml.t3.2xlarge',
                'ml.m5.large', 'ml.m5.xlarge', 'ml.m5.2xlarge', 'ml.m5.4xlarge',
                'ml.c5.large', 'ml.c5.xlarge', 'ml.c5.2xlarge',
                'ml.p3.2xlarge', 'ml.p3.8xlarge'
            ],
            'Lambda': ['requests', 'duration'],
            'CloudFront': ['standard', 'price_class_100', 'price_class_200'],
            'ElastiCache': [
                'cache.t3.micro', 'cache.t3.small', 'cache.t3.medium',
                'cache.m5.large', 'cache.m5.xlarge', 'cache.r5.large'
            ],
            'OpenSearch': [
                't3.small.search', 't3.medium.search', 'm5.large.search', 'm5.xlarge.search'
            ]
        }
        
        priced_services = []
        for service in services:
            service_name = service['name']
            print(f"\n=== Processing {service_name} ===\n")
            
            if service_name in service_options:
                options = []
                for option in service_options[service_name]:
                    price = self.get_pricing(service_name, option, region)
                    if price is not None:
                        options.append({
                            'type': option,
                            'monthly_cost': price,
                            'reason': service['reason']
                        })
                
                if options:
                    sorted_options = sorted(options, key=lambda x: x['monthly_cost'])
                    priced_services.append({
                        'name': service_name,
                        'reason': service['reason'],
                        'options': sorted_options
                    })
                    
                    print(f"\n{service_name} pricing completed:")
                    for i, opt in enumerate(sorted_options[:5]):
                        print(f"  {i+1}. {opt['type']}: ${opt['monthly_cost']}/month")
                    print(f"  Total {len(sorted_options)} options available\n")
        
        print(f"\n=== Step 2 Complete: {len(priced_services)} services priced ===\n")
        return priced_services
    
    def step3_optimize_for_budget(self, priced_services, budget):
        """3단계: AI를 통한 예산 최적화"""
        try:
            # 서비스 옵션 정보를 AI에게 전달
            services_info = []
            for service in priced_services:
                service_options = []
                for option in service['options']:
                    service_options.append(f"{option['type']}: ${option['monthly_cost']}/월")
                
                services_info.append({
                    'name': service['name'],
                    'reason': service['reason'],
                    'options': service_options
                })
            
            bedrock_prompt = f"""
            AWS 예산 최적화 요청:
            - 예산: ${budget}/월
            - 사용 가능한 서비스와 가격:
            {json.dumps(services_info, ensure_ascii=False, indent=2)}
            
            예산 내에서 최대 성능을 낼 수 있는 서비스 조합을 선택해주세요.
            각 서비스마다 가장 적절한 인스턴스 타입을 선택하고, 예산을 초과하지 마세요.
            
            응답 형식:
            {{
                "optimized_services": [
                    {{"name": "EC2", "type": "t3.medium", "monthly_cost": 38, "reason": "웹서버 (성능 최적화)", "quantity": 1}}
                ],
                "total_cost": 150,
                "explanation": "예산 내에서 최대 성능을 위해 선택한 이유"
            }}
            """
            
            body = json.dumps({
                "messages": [{
                    "role": "user", 
                    "content": [{"text": bedrock_prompt}]
                }],
                "inferenceConfig": {
                    "max_new_tokens": 32768,
                    "temperature": 0.3
                }
            })
            
            response = bedrock.invoke_model(
                modelId="us.amazon.nova-premier-v1:0",
                body=body,
                contentType="application/json"
            )

            print(response['body'].read().decode('utf-8'))
            
            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                optimization = json.loads(content[start:end])
                return optimization['optimized_services'], optimization['total_cost']
                
        except Exception as e:
            print(f"Step 3 AI optimization failed: {e}")
        
        # AI 실패 시 기본 최적화
        return self._fallback_optimization(priced_services, budget)
    
    def _fallback_optimization(self, priced_services, budget):
        """기본 최적화 로직"""
        optimized = []
        total_cost = 0
        
        for service in priced_services:
            if service['options']:
                cheapest = service['options'][0]
                if total_cost + cheapest['monthly_cost'] <= budget:
                    optimized.append({
                        'name': service['name'],
                        'type': cheapest['type'],
                        'monthly_cost': cheapest['monthly_cost'],
                        'reason': cheapest['reason'],
                        'quantity': 1
                    })
                    total_cost += cheapest['monthly_cost']
        
        return optimized, total_cost
    
    def analyze_requirements(self, service_type, users, performance, additional_info, budget, region='us-east-1'):
        """3단계 최적화 프로세스 실행"""
        # 1단계: 필요 서비스 목록 추출
        required_services = self.step1_get_required_services(service_type, users, performance, additional_info, region)
        
        # 2단계: 서비스별 가격 조회
        priced_services = self.step2_get_service_prices(required_services, region)
        
        # 3단계: 예산에 맞는 최적화
        optimized_services, total_cost = self.step3_optimize_for_budget(priced_services, budget)
        
        return optimized_services, total_cost
    
    def _fallback_services(self, service_type):
        """AI 실패 시 기본 서비스 목록"""
        if service_type in ['웹사이트', 'API'] or 'web' in service_type.lower():
            return [
                {'name': 'EC2', 'reason': '웹서버'},
                {'name': 'RDS', 'reason': '데이터베이스'}
            ]
        elif service_type == '데이터베이스':
            return [{'name': 'RDS', 'reason': '데이터베이스'}]
        elif service_type == '머신러닝':
            return [
                {'name': 'EC2', 'reason': 'ML 워크로드'},
                {'name': 'S3', 'reason': '데이터 저장소'}
            ]
        else:
            return [{'name': 'EC2', 'reason': '기본 서버'}]

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
        
        # 3단계 최적화 프로세스 실행
        optimized_services, total_cost = optimizer.analyze_requirements(service_type, users, performance, additional_info, budget, region)
        
        store_request(request_uuid, {
            'status': 'optimizing',
            'services_analyzed': optimized_services,
            'updated_at': datetime.utcnow()
        })
        
        # 결과 생성
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