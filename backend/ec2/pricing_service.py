import boto3
import json
from typing import Dict, List, Optional
from decimal import Decimal

class AWSPricingService:
    def __init__(self):
        self.pricing = boto3.client('pricing', region_name='us-east-1')
    
    def get_ec2_pricing(self, instance_type: str, region: str = 'us-east-1') -> Optional[float]:
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'operating-system', 'Value': 'Linux'}
                ]
            )
            
            if response['PriceList']:
                price_item = json.loads(response['PriceList'][0])
                on_demand = price_item['terms']['OnDemand']
                price_dimensions = list(on_demand.values())[0]['priceDimensions']
                hourly_price = float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
                return hourly_price * 24 * 30  # 월 비용
                
        except Exception as e:
            print(f"EC2 pricing error: {e}")
        
        return None
    
    def get_rds_pricing(self, instance_type: str, engine: str = 'mysql') -> Optional[float]:
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonRDS',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
                    {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'}
                ]
            )
            
            if response['PriceList']:
                price_item = json.loads(response['PriceList'][0])
                on_demand = price_item['terms']['OnDemand']
                price_dimensions = list(on_demand.values())[0]['priceDimensions']
                hourly_price = float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
                return hourly_price * 24 * 30
                
        except Exception as e:
            print(f"RDS pricing error: {e}")
        
        return None
    
    def get_service_estimates(self, services: List[str]) -> Dict[str, float]:
        estimates = {}
        
        service_defaults = {
            'EC2': {'type': 't3.micro', 'cost': 8.5},
            'RDS': {'type': 'db.t3.micro', 'cost': 15.0},
            'S3': {'type': 'standard', 'cost': 5.0},
            'CloudFront': {'type': 'standard', 'cost': 10.0},
            'Lambda': {'type': '1M requests', 'cost': 2.0},
            'DynamoDB': {'type': 'on-demand', 'cost': 12.0},
            'API Gateway': {'type': '1M requests', 'cost': 3.5}
        }
        
        for service in services:
            if service in service_defaults:
                default = service_defaults[service]
                
                if service == 'EC2':
                    actual_cost = self.get_ec2_pricing(default['type'])
                elif service == 'RDS':
                    actual_cost = self.get_rds_pricing(default['type'])
                else:
                    actual_cost = None
                
                estimates[service] = actual_cost or default['cost']
        
        return estimates
    
    def _get_location_name(self, region: str) -> str:
        region_mapping = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)'
        }
        return region_mapping.get(region, 'US East (N. Virginia)')