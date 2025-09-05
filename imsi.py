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
            'RDS_READ_REPLICA': {'db.t3.micro': 15, 'db.t3.small': 30, 'db.t3.medium': 60, 'db.t3.large': 120},
            'S3': {'standard': 23, 'intelligent_tiering': 23},
            'ALB': {'application': 22},
            'SageMaker': {'ml.t3.medium': 45},
            'Lambda': {'requests': 0.2, 'gb_seconds': 16.67}
        }
    
    def get_pricing(self, service, instance_type, region='us-east-1'):
        cache_key = f"{service}_{instance_type}_{region}"
        if cache_key in self.pricing_cache:
            return self.pricing_cache[cache_key]
        
        try:
            price = self._get_aws_service_price(service, instance_type, region)
            self.pricing_cache[cache_key] = price
            return price
        except Exception as e:
            print(f"Pricing API failed for {service} {instance_type}: {e}")
            fallback = self.fallback_costs.get(service, {}).get(instance_type, 50)
            self.pricing_cache[cache_key] = fallback
            return fallback
    
    def _get_aws_service_price(self, service, instance_type, region):
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-southeast-1': 'Asia Pacific (Singapore)'
        }
        
        # 서비스별 설정
        service_configs = {
            'EC2': {
                'ServiceCode': 'AmazonEC2',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                ]
            },
            'RDS': {
                'ServiceCode': 'AmazonRDS',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'},
                    {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'}
                ]
            },
            'RDS_READ_REPLICA': {
                'ServiceCode': 'AmazonRDS',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'}
                ]
            },
            'ALB': {
                'ServiceCode': 'AWSELB',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Load Balancer-Application'}
                ]
            },
            'SageMaker': {
                'ServiceCode': 'AmazonSageMaker',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type}
                ]
            },
            'S3': {
                'ServiceCode': 'AmazonS3',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'storageClass', 'Value': 'General Purpose'}
                ]
            },
            'Lambda': {
                'ServiceCode': 'AWSLambda',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'group', 'Value': 'AWS-Lambda-Requests'}
                ]
            },
            'CloudFront': {
                'ServiceCode': 'AmazonCloudFront',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Data Transfer'}
                ]
            }
        }
        
        if service not in service_configs:
            return self.fallback_costs.get(service, {}).get(instance_type, 50)
        
        config = service_configs[service]
        filters = config['filters'].copy()
        
        # 위치 필터 추가
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
            
            # OnDemand 가격 추출
            if 'terms' in price_data and 'OnDemand' in price_data['terms']:
                terms = price_data['terms']['OnDemand']
                for term_key in terms:
                    price_dimensions = terms[term_key]['priceDimensions']
                    for pd_key in price_dimensions:
                        price_per_unit = price_dimensions[pd_key]['pricePerUnit']['USD']
                        if price_per_unit and float(price_per_unit) > 0:
                            hourly_price = float(price_per_unit)
                            
                            # 서비스별 월 비용 계산
                            if service in ['EC2', 'RDS', 'RDS_READ_REPLICA', 'SageMaker']:
                                return hourly_price * 24 * 30  # 시간당 → 월
                            elif service == 'ALB':
                                return hourly_price * 24 * 30 + 22.5  # ALB 기본 요금
                            elif service == 'S3':
                                return hourly_price * 1000  # GB당 → 월 (1TB 기준)
                            else:
                                return hourly_price * 24 * 30
        
        return self.fallback_costs.get(service, {}).get(instance_type, 50)
    
    def analyze_requirements(self, service_type, users, performance, additional_info, budget, region='us-east-1'):
        try:
            bedrock_prompt = f"""
            # 목적
            - 당신은 서버 설계를 위해서, Traffic 입장에서 어떤 일이 있을때 어떤 특성으로 트래픽이 나올지 예측하는 모델입니다.
            # 입력
            - 유저로부터 어떤 서비스를 만들고자 하는지에 대해 입력받게 됩니다. 
            # 출력
            - 당신은 제공받은 입력의 서비스가 어떤 이벤트가 발생하면 어떤 특성을 가지는 Traffic이 얼마나 생길지 예측하여 그 최고로 많은 량의 트래픽 시나리오를 작성하면 됩니다. 
            - 당신은 유저에게 추가정보를 받을 수 없습니다. 따라서, 당신은 무조건, **한번의 질문에서 모든 상황과 목적을 추론하여 생성해야 합니다.**
            - Traffic의 최대 폭발량은 1000배 혹은 10000 request per day중 가장 높은 값을 선택하면 됩니다.
            - 당신은 최악의 단계의 서버에 필요한 특성과 필요한 리소스들을 제시하면 됩니다. 이때, 트래픽의 특성을 제시하세요.
            - 또한 가능하다면, 당신은 AWS의 자원을 활용하여 리소스의 답을 제시하여야 합니다. 이 점에 유의하세요.
            
            AWS 서비스 추천 요청:
            - 서비스 유형: {service_type}
            - 예상 사용자 수: {users}
            - 성능 요구사항: {performance}
            - 추가 요구사항: {additional_info}
            - 예산: ${budget}/월
            - 리전: {region}
            
            On-Demand 인스턴스 타입을 사용하며, 최대한 예산 범위 내에서 "최대한 크게 넉넉히" 추천합니다.
            
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
                modelId="us.amazon.nova-premier-v1:0",
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
            # 사용자 규모에 따른 EC2 인스턴스 선택
            if user_scale == 'small':  # 1-100명
                ec2_type = 't2.micro'
                instance_count = 1
            elif user_scale == 'medium':  # 100-1,000명
                ec2_type = 't2.small'
                instance_count = 1
            elif user_scale == 'large':  # 1,000-10,000명
                ec2_type = 't2.medium'
                instance_count = 2  # 로드 밸런싱을 위한 다중 인스턴스
            else:  # 엔터프라이즈 10,000명+
                ec2_type = 't3.large'
                instance_count = 3
            
            # 성능 요구사항에 따른 인스턴스 업그레이드
            if performance in ['고성능', '최고성능']:
                if ec2_type == 't2.micro':
                    ec2_type = 't2.small'
                elif ec2_type == 't2.small':
                    ec2_type = 't2.medium'
                elif ec2_type == 't2.medium':
                    ec2_type = 't3.medium'
            
            services.append({
                "name": "EC2", 
                "type": ec2_type, 
                "quantity": instance_count, 
                "reason": f"웹서버/API서버 ({users} 사용자 대응)"
            })
            
            # 로드 밸런서 추가 (대규모 이상)
            if user_scale in ['large', 'enterprise']:
                services.append({
                    "name": "ALB", 
                    "type": "application", 
                    "quantity": 1, 
                    "reason": "로드 밸런싱 및 고가용성"
                })
            
            # 데이터베이스 추가 (사용자 규모에 따른 크기 조정)
            if '데이터베이스' in additional_info or service_type == '웹사이트':
                if user_scale == 'small':
                    rds_type = 'db.t3.micro'
                elif user_scale == 'medium':
                    rds_type = 'db.t3.small'
                elif user_scale == 'large':
                    rds_type = 'db.t3.medium'
                else:  # enterprise
                    rds_type = 'db.t3.large'
                
                services.append({
                    "name": "RDS", 
                    "type": rds_type, 
                    "quantity": 1, 
                    "reason": f"데이터베이스 ({users} 사용자 대응)"
                })
        
        elif service_type == '데이터베이스' or 'database' in service_type.lower() or 'db' in service_type.lower():
            # 사용자 규모에 따른 데이터베이스 크기 선택
            if user_scale == 'small':
                rds_type = 'db.t3.micro'
                read_replicas = 0
            elif user_scale == 'medium':
                rds_type = 'db.t3.small'
                read_replicas = 1
            elif user_scale == 'large':
                rds_type = 'db.t3.medium'
                read_replicas = 2
            else:  # enterprise
                rds_type = 'db.t3.large'
                read_replicas = 3
            
            services.append({
                "name": "RDS", 
                "type": rds_type, 
                "quantity": 1, 
                "reason": f"메인 데이터베이스 ({users} 사용자 대응)"
            })
            
            # 읽기 전용 복제본 추가 (중간규모 이상)
            if read_replicas > 0:
                services.append({
                    "name": "RDS_READ_REPLICA", 
                    "type": rds_type, 
                    "quantity": read_replicas, 
                    "reason": f"읽기 성능 향상을 위한 복제본"
                })
        
        elif service_type == '머신러닝' or any(word in service_type.lower() for word in ['ml', 'ai', 'machine', 'learning']):
            # ML 워크로드는 사용자 수보다 데이터 처리량에 따라 결정
            if user_scale in ['small', 'medium']:
                ec2_type = 't3.medium'
            else:
                ec2_type = 't3.large'
            
            services.append({
                "name": "EC2", 
                "type": ec2_type, 
                "quantity": 1, 
                "reason": f"ML 워크로드 ({users} 사용자 대응)"
            })
            services.append({
                "name": "S3", 
                "type": "standard", 
                "quantity": 1, 
                "reason": "ML 데이터 저장소"
            })
            
            # 대규모 ML 워크로드에 SageMaker 추가
            if user_scale in ['large', 'enterprise']:
                services.append({
                    "name": "SageMaker", 
                    "type": "ml.t3.medium", 
                    "quantity": 1, 
                    "reason": "대규모 ML 모델 학습 및 배포"
                })
        
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
            'EC2': ['t2.nano', 't2.micro', 't2.small', 't2.medium'],
            'RDS': ['db.t3.micro', 'db.t3.small', 'db.t3.medium'],
            'RDS_READ_REPLICA': ['db.t3.micro', 'db.t3.small', 'db.t3.medium'],
            'ALB': ['application'],
            'SageMaker': ['ml.t3.medium']
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
    
    # {"service_type":"API","users":"엔터프라이즈","performance":"최고성능","additional_info":"","budget":1000000,"region":"ap-northeast-2"}
    service_type = data.get('service_type', '')
    users = data.get('users', '선택안됨')
    performance = data.get('performance', '선택안됨')
    additional_info = data.get('additional_info', '정보없음')
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

@app.route('/contact', methods=['POST'])
def submit_contact():
    data = request.json
    contact_uuid = str(uuid.uuid4())
    
    # 문의 데이터 저장
    contact_data = {
        'uuid': contact_uuid,
        'name': data.get('name'),
        'email': data.get('email'),
        'subject': data.get('subject'),
        'message': data.get('message'),
        'timestamp': data.get('timestamp'),
        'status': 'received'
    }
    
    # 메모리에 저장 (실제로는 데이터베이스 사용)
    requests_store[f'contact_{contact_uuid}'] = contact_data
    
    print(f"New contact received: {contact_data['name']} - {contact_data['subject']}")
    
    return jsonify({'status': 'success', 'uuid': contact_uuid})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)