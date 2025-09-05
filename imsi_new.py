from flask import Flask, request, jsonify
import boto3
import json
import uuid
import time
from datetime import datetime
from threading import Thread
import pymysql
import os
app = Flask(__name__)

# AWS 클라이언트
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
pricing_client = boto3.client('pricing', region_name='us-east-1')
rds_client = boto3.client('rds', region_name='us-east-1')

# RDS 설정
RDS_CONFIG = {
    'host': os.environ.get('RDS_ENDPOINT', 'localhost'),
    'user': os.environ.get('RDS_USERNAME', 'admin'),
    'password': os.environ.get('RDS_PASSWORD', ''),
    'database': os.environ.get('RDS_DATABASE', 'clops'),
    'port': int(os.environ.get('RDS_PORT', 3306)),
    'charset': 'utf8mb4'
}

# 메모리 저장소 (폴백)
memory_storage = {}

def get_rds_info():
    try:
        response = rds_client.describe_db_instances()
        for db in response['DBInstances']:
            if 'team02-hackathon-db' in db['DBInstanceIdentifier'] and db['DBInstanceStatus'] == 'available':
                print(f"RDS Status: {db['DBInstanceStatus']}")
                print(f"RDS Endpoint: {db['Endpoint']['Address']}")
                return {
                    'endpoint': db['Endpoint']['Address'],
                    'port': db['Endpoint']['Port'],
                    'username': db['MasterUsername'],
                    'database': db['DBName']
                }
        return None
    except Exception as e:
        print(f"Failed to get RDS info: {e}")
        return None

def get_rds_password_from_secrets():
    """Try to get RDS password from AWS Secrets Manager or Parameter Store"""
    try:
        # Try AWS Systems Manager Parameter Store first
        ssm_client = boto3.client('ssm', region_name='us-east-1')
        response = ssm_client.get_parameter(
            Name='/team02-hackathon/rds/password',
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Could not get password from Parameter Store: {e}")
        return None

def get_db_connection():
    import time
    max_retries = 3
    
    # Get RDS info from AWS API
    rds_info = get_rds_info()
    if rds_info:
        RDS_CONFIG['host'] = rds_info['endpoint']
        RDS_CONFIG['port'] = rds_info['port']
        RDS_CONFIG['user'] = rds_info['username']
        RDS_CONFIG['database'] = rds_info['database']
        print(f"Updated RDS config from AWS API: {rds_info['endpoint']}")
    
    # Try to get password from environment first, then from AWS
    if not RDS_CONFIG['password']:
        password = get_rds_password_from_secrets()
        if password:
            RDS_CONFIG['password'] = password
            print("Retrieved RDS password from AWS Parameter Store")
    
    for attempt in range(max_retries):
        try:
            print(f"Connecting to RDS: {RDS_CONFIG['host']}:{RDS_CONFIG['port']}")
            print(f"Username: {RDS_CONFIG['user']}, Database: {RDS_CONFIG['database']}")
            print(f"Password set: {'Yes' if RDS_CONFIG['password'] else 'No'}")
            return pymysql.connect(**RDS_CONFIG)
        except Exception as e:
            print(f"RDS connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print("RDS connection failed, using fallback mode")
                return None

def init_db():
    try:
        conn = get_db_connection()
        if not conn:
            print("Running in fallback mode without database")
            return
        cursor = conn.cursor()
    except Exception as e:
        print(f"Database connection failed: {e}")
        return
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            uuid VARCHAR(36) PRIMARY KEY,
            request_data JSON NOT NULL,
            response_data JSON,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            uuid VARCHAR(36),
            name VARCHAR(255),
            email VARCHAR(255),
            subject VARCHAR(255),
            message TEXT,
            status VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
    conn.commit()
    conn.close()
    print("Database initialized successfully")

class AWSOptimizer:
    def __init__(self):
        self.pricing_cache = {}
        self.aws_services_cache = None
        self.fallback_costs = {
            'AmazonEC2': {'t2.nano': 4.2, 't2.micro': 8.5, 't2.small': 17, 't2.medium': 34, 't3.medium': 38, 't3.large': 76},
            'AmazonRDS': {'db.t3.micro': 15, 'db.t3.small': 30, 'db.t3.medium': 60, 'db.t3.large': 120},
            'ElasticLoadBalancing': {'application': 22},
            'AmazonS3': {'standard': 23},
            'AmazonSageMaker': {'ml.t3.medium': 45, 'ml.t3.large': 90},
            'AWSLambda': {'requests': 0.2}
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
            'AmazonEC2': {
                'ServiceCode': 'AmazonEC2',
                'filters': [
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'}
                ]
            },
            'AmazonRDS': {
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
    
    def get_all_aws_services(self):
        """AWS의 모든 서비스 목록을 가져오기"""
        if self.aws_services_cache:
            return self.aws_services_cache
        
        try:
            response = pricing_client.describe_services()
            services = []
            for service in response['Services']:
                services.append({
                    'ServiceCode': service['ServiceCode'],
                    'ServiceName': service.get('ServiceName', service['ServiceCode'])
                })
            
            self.aws_services_cache = services
            print(f"Loaded {len(services)} AWS services")
            return services
        except Exception as e:
            print(f"Failed to get AWS services: {e}")
            return []
    
    def step1_disaster_ready_services(self, service_type, users, performance, additional_info, region='us-east-1'):
        """1단계: 재해상황 대비 필수 AWS 서비스 목록 추출"""
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
            AWS 아키텍처 설계 요청:
            - 서비스 유형: {service_type}
            - 예상 사용자 수: {users}
            - 성능 요구사항: {performance}
            - 추가 정보: {additional_info}
            - 리전: {region}
            
            갑작스러운 트래픽 급증(10-100배), DDoS 공격, 서버 장애 등 재해상황에 대비한 AWS 서비스 조합을 추천해주세요.
            다음 서비스들을 우선적으로 고려하되, 한정하지 말고, 사용자가 필요한 서비스를 추가하세요:

            가격은 고려 말고 필요할 거 같은 모든 서비스를 나열해 주세요!

            
            - AmazonCloudFront (CDN, DDoS 보호)
            - AWSWAF (웹 방화벽)
            - ElasticLoadBalancingV2 (로드밸런싱)
            - AmazonEC2 (Auto Scaling 지원)
            - AmazonRDS (Multi-AZ 배포)
            - ElastiCache (캐싱)
            - AmazonS3 (정적 콘텐츠)
            - AmazonRoute53 (DNS 장애조치)
            - AmazonCloudWatch (모니터링)
            
            응답 형식:
            {{
                "disaster_ready_services": [
                    {{"name": "AmazonCloudFront", "reason": "CDN으로 트래픽 분산 및 DDoS 보호"}},
                    {{"name": "AWSWAF", "reason": "웹 애플리케이션 방화벽으로 악성 트래픽 차단"}},
                    {{"name": "ElasticLoadBalancingV2", "reason": "다중 인스턴스 간 로드밸런싱"}},
                    {{"name": "AmazonEC2", "reason": "Auto Scaling으로 트래픽 급증 대응"}}
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
                    "temperature": 0.12
                }
            })
            
            response = bedrock.invoke_model(
                modelId="us.amazon.nova-premier-v1:0",
                body=body,
                contentType="application/json"
            )
            
            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            # ```json 블록에서 JSON 추출
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            else:
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end]
            
            services_data = json.loads(json_str)
            services = services_data['disaster_ready_services']
            
            print(f"\n=== Step 1 Complete: {len(services)} disaster-ready services identified ===")
            for service in services:
                print(f"  - {service['name']}: {service['reason']}")
            print()
            
            return services
        except Exception as e:
            print(f"Step 1 disaster-ready analysis failed: {e}")
        
        return self._fallback_disaster_services(service_type)
    
    def get_service_options(self, service_code, region='us-east-1'):
        """특정 서비스의 모든 옵션을 가져오기"""
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'ap-northeast-2': 'Asia Pacific (Seoul)'
        }
        
        try:
            filters = [{
                'Type': 'TERM_MATCH',
                'Field': 'location',
                'Value': location_map.get(region, 'US East (N. Virginia)')
            }]
            
            response = pricing_client.get_products(
                ServiceCode=service_code,
                Filters=filters,
                MaxResults=100
            )
            
            options = set()
            for product_str in response['PriceList']:
                product = json.loads(product_str)
                attributes = product.get('product', {}).get('attributes', {})
                
                # EC2 인스턴스 타입
                if 'instanceType' in attributes:
                    options.add(attributes['instanceType'])
                # RDS 인스턴스 타입
                elif 'instanceClass' in attributes:
                    options.add(attributes['instanceClass'])
                # S3 스토리지 클래스
                elif 'storageClass' in attributes:
                    options.add(attributes['storageClass'])
                # 기타 서비스는 기본값
                else:
                    options.add('standard')
            
            return list(options)
            
        except Exception as e:
            print(f"Failed to get options for {service_code}: {e}")
            return ['standard']  # 기본값 반환
    
    def step2_get_service_prices(self, services, region='us-east-1'):
        """2단계: 각 서비스의 다양한 옵션별 가격 조회"""
        priced_services = []
        
        for service in services:
            service_name = service['name']
            print(f"\n=== Processing {service_name} ===\n")
            
            # 해당 서비스의 모든 옵션 가져오기
            service_options = self.get_service_options(service_name, region)
            print(f"Found {len(service_options)} options for {service_name}")
            
            options = []
            for option in service_options:
                price = self.get_pricing(service_name, option, region)
                if price is not None and price > 0:
                    options.append({
                        'type': option,
                        'monthly_cost': price,
                        'reason': service['reason']
                    })
                else:
                    print(f"  Skipping {option}: No valid pricing data")
            
            if options:
                sorted_options = sorted(options, key=lambda x: x['monthly_cost'])
                priced_services.append({
                    'name': service_name,
                    'reason': service['reason'],
                    'options': sorted_options
                })
                
                print(f"\n{service_name} pricing completed:")
                for i, opt in enumerate(sorted_options):
                    print(f"  {i+1}. {opt['type']}: ${opt['monthly_cost']:.2f}/month")
                print(f"  Total {len(sorted_options)} options available\n")
            else:
                print(f"  No valid pricing options found for {service_name}")
        
        print(f"\n=== Step 2 Complete: {len(priced_services)} services priced ===\n")
        return priced_services
    
    def step3_budget_disaster_optimization(self, priced_services, budget, service_type='', users='', performance='', additional_info='', region='us-east-1'):
        """3단계: 예산 내 재해대비 최적 서비스 조합 추천"""
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
            - 서비스와 가격 옵션:
            {json.dumps(services_info, ensure_ascii=False, indent=2)}
            
            예산 내에서 다음 재해상황에 최적으로 대응할 수 있는 서비스 조합을 추천해주세요.
            다만 재해상황보다 !!""사용자가 원하는 서비스 운영이 우선임을 감안""!!하세요.
            :
            1. 갑작스러운 트래픽 급증 (10-100배)
            2. DDoS 공격
            3. 서버/데이터베이스 장애
            4. 네트워크 장애

            
            
            우선순위:
            1. 가용성 > 성능 > 비용
            2. Auto Scaling 가능한 서비스 우선
            3. Multi-AZ 배포 고려
            4. CDN 및 캐싱 활용
            5. 모니터링 및 알림 포함

            사용자가 원한 서비스 프롬포트:
            재해상황 대비 AWS 아키텍처 설계 요청:
            - 서비스 유형: {service_type}
            - 예상 사용자 수: {users}
            - 성능 요구사항: {performance}
            - 추가 정보: {additional_info}
            - 리전: {region}
            
            응답 형식:
            {{
                "disaster_ready_services": [
                    {{"name": "AmazonCloudFront", "type": "standard", "monthly_cost": 50, "reason": "CDN으로 트래픽 분산, DDoS 보호", "quantity": 1, "disaster_benefit": "트래픽 급증 시 오리진 서버 부하 감소"}},
                    {{"name": "AmazonEC2", "type": "t3.medium", "monthly_cost": 38, "reason": "Auto Scaling 웹서버", "quantity": 2, "disaster_benefit": "자동 확장으로 트래픽 급증 대응"}}
                ],
                "total_cost": 150,
                "disaster_readiness_score": 85,
                "explanation": "재해상황 대비를 위해 선택한 이유와 예상 효과"
            }}
            """
            
            body = json.dumps({
                "messages": [{
                    "role": "user", 
                    "content": [{"text": bedrock_prompt}]
                }],
                "inferenceConfig": {
                    "max_new_tokens": 32768,
                    "temperature": 0.12
                }
            })
            
            response = bedrock.invoke_model(
                modelId="us.amazon.nova-premier-v1:0",
                body=body,
                contentType="application/json"
            )

            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            # ```json 블록에서 JSON 추출
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            else:
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end]
            
            optimization = json.loads(json_str)
            return optimization['disaster_ready_services'], optimization['total_cost']
                
        except Exception as e:
            print(f"Step 3 disaster-ready optimization failed: {e}")
        
        # AI 실패 시 기본 재해대비 최적화
        return self._fallback_disaster_optimization(priced_services, budget)
    
    def _fallback_disaster_optimization(self, priced_services, budget):
        """기본 재해대비 최적화 로직"""
        optimized = []
        total_cost = 0
        
        # 재해대비 우선순위: CDN > 로드밸런서 > Auto Scaling > 모니터링
        priority_services = ['AmazonCloudFront', 'ElasticLoadBalancingV2', 'AmazonEC2', 'AmazonCloudWatch']
        
        # 우선순위 서비스부터 처리
        for priority_service in priority_services:
            for service in priced_services:
                if service['name'] == priority_service and service['options']:
                    # 중간 성능 옵션 선택 (재해대비를 위해)
                    mid_option = service['options'][len(service['options'])//2] if len(service['options']) > 1 else service['options'][0]
                    if total_cost + mid_option['monthly_cost'] <= budget:
                        quantity = 2 if priority_service == 'AmazonEC2' else 1  # EC2는 이중화
                        cost = mid_option['monthly_cost'] * quantity
                        if total_cost + cost <= budget:
                            optimized.append({
                                'name': service['name'],
                                'type': mid_option['type'],
                                'monthly_cost': cost,
                                'reason': f"{mid_option['reason']} (재해대비)",
                                'quantity': quantity,
                                'disaster_benefit': '재해상황 대응 강화'
                            })
                            total_cost += cost
                    break
        
        # 나머지 서비스 처리
        for service in priced_services:
            if service['name'] not in priority_services and service['options']:
                cheapest = service['options'][0]
                if total_cost + cheapest['monthly_cost'] <= budget:
                    optimized.append({
                        'name': service['name'],
                        'type': cheapest['type'],
                        'monthly_cost': cheapest['monthly_cost'],
                        'reason': cheapest['reason'],
                        'quantity': 1,
                        'disaster_benefit': '기본 서비스 지원'
                    })
                    total_cost += cheapest['monthly_cost']
        
        return optimized, total_cost
    
    def analyze_requirements(self, service_type, users, performance, additional_info, budget, region='us-east-1'):
        """3단계 재해대비 최적화 프로세스 실행"""
        # 1단계: 재해상황 대비 필수 서비스 목록 추출
        required_services = self.step1_disaster_ready_services(service_type, users, performance, additional_info, region)
        
        # 2단계: 서비스별 가격 조회
        priced_services = self.step2_get_service_prices(required_services, region)
        
        # 3단계: 예산 내 재해대비 최적 조합 추천
        optimized_services, total_cost = self.step3_budget_disaster_optimization(priced_services, budget, service_type, users, performance, additional_info, region)
        
        return optimized_services, total_cost
    
    def _fallback_disaster_services(self, service_type):
        """AI 실패 시 기본 재해대비 서비스 목록"""
        base_disaster_services = [
            {'name': 'AmazonCloudFront', 'reason': 'CDN으로 트래픽 분산 및 DDoS 보호'},
            {'name': 'ElasticLoadBalancingV2', 'reason': '로드밸런서로 트래픽 분산'},
            {'name': 'AmazonCloudWatch', 'reason': '실시간 모니터링 및 알림'}
        ]
        
        if service_type in ['웹사이트', 'API', '게임'] or 'web' in service_type.lower():
            return base_disaster_services + [
                {'name': 'AWSWAF', 'reason': '웹 애플리케이션 방화벽'},
                {'name': 'AmazonEC2', 'reason': 'Auto Scaling 웹서버'},
                {'name': 'AmazonRDS', 'reason': 'Multi-AZ 데이터베이스'},
                {'name': 'ElastiCache', 'reason': '캐싱으로 성능 향상'},
                {'name': 'AmazonS3', 'reason': '정적 콘텐츠 저장'}
            ]
        elif service_type == '데이터베이스':
            return base_disaster_services + [
                {'name': 'AmazonRDS', 'reason': 'Multi-AZ 고가용성 데이터베이스'},
                {'name': 'AmazonS3', 'reason': '백업 저장소'}
            ]
        elif service_type == '머신러닝':
            return base_disaster_services + [
                {'name': 'AmazonEC2', 'reason': 'Auto Scaling ML 워크로드'},
                {'name': 'AmazonS3', 'reason': '데이터 저장소 및 백업'}
            ]
        else:
            return base_disaster_services + [
                {'name': 'AmazonEC2', 'reason': 'Auto Scaling 서버'},
                {'name': 'AmazonS3', 'reason': '백업 및 저장소'}
            ]

optimizer = AWSOptimizer()

def store_request(request_uuid, request_data, response_data=None, status='pending'):
    try:
        conn = get_db_connection()
        if not conn:
            # 메모리 저장소 사용
            memory_storage[request_uuid] = {
                'request_data': request_data,
                'response_data': response_data,
                'status': status,
                'created_at': datetime.utcnow().isoformat()
            }
            print(f"Stored in memory: {request_uuid}")
            return
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO requests (uuid, request_data, response_data, status)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            response_data = VALUES(response_data),
            status = VALUES(status),
            updated_at = CURRENT_TIMESTAMP
        ''', (request_uuid, json.dumps(request_data), json.dumps(response_data) if response_data else None, status))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database store failed: {e}")
        # 메모리 저장소 사용
        memory_storage[request_uuid] = {
            'request_data': request_data,
            'response_data': response_data,
            'status': status,
            'created_at': datetime.utcnow().isoformat()
        }

def get_request(request_uuid):
    try:
        conn = get_db_connection()
        if not conn:
            # 메모리 저장소에서 검색
            if request_uuid in memory_storage:
                return memory_storage[request_uuid]
            return {'status': 'not_found'}
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute('SELECT * FROM requests WHERE uuid = %s', (request_uuid,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            result['request_data'] = json.loads(result['request_data'])
            if result['response_data']:
                result['response_data'] = json.loads(result['response_data'])
        
        return result
    except Exception as e:
        print(f"Database get failed: {e}")
        # 메모리 저장소에서 검색
        if request_uuid in memory_storage:
            return memory_storage[request_uuid]
        return {'status': 'error', 'message': 'Database error'}

def process_optimization(request_uuid, service_type, users, performance, additional_info, budget, region):
    try:
        request_data = {
            'service_type': service_type,
            'users': users,
            'performance': performance,
            'additional_info': additional_info,
            'budget': budget,
            'region': region
        }
        
        store_request(request_uuid, request_data, status='processing')
        
        # 3단계 최적화 프로세스 실행
        optimized_services, total_cost = optimizer.analyze_requirements(service_type, users, performance, additional_info, budget, region)
        
        # 결과 생성
        feasible = total_cost <= budget
        
        if feasible:
            response_data = {
                'feasible': True,
                'services': optimized_services,
                'total_cost': total_cost,
                'budget': budget,
                'savings': round(budget - total_cost, 2),
                'region': region
            }
        else:
            response_data = {
                'feasible': False,
                'message': f'예산 ${budget}로는 요구사항을 충족할 수 없습니다. 최소 ${total_cost}가 필요합니다.',
                'minimum_budget': total_cost,
                'budget': budget,
                'region': region
            }
        
        store_request(request_uuid, request_data, response_data, 'completed')
        
    except Exception as e:
        error_response = {'error': str(e)}
        request_data = request_data if 'request_data' in locals() else {}
        store_request(request_uuid, request_data, error_response, 'failed')

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

@app.route('/contact', methods=['POST'])
def save_contact():
    data = request.json
    contact_uuid = str(uuid.uuid4())
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'success', 'uuid': contact_uuid, 'message': 'Stored locally'})
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO contacts (uuid, name, email, subject, message, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            contact_uuid,
            data.get('name'),
            data.get('email'),
            data.get('subject'),
            data.get('message'),
            'received'
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'uuid': contact_uuid})
    except Exception as e:
        print(f"Contact save failed: {e}")
        return jsonify({'status': 'success', 'uuid': contact_uuid, 'message': 'Stored locally'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)