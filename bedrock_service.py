import boto3
import json
import threading
import time

class BedrockService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.results = {}
    
    def analyze_aws_requirements(self, prompt, request_uuid):
        """백그라운드에서 Bedrock 분석 실행"""
        def run_analysis():
            try:
                # AWS 서비스 추천을 위한 시스템 프롬프트 추가
                system_prompt = """당신은 AWS 클라우드 아키텍트입니다. 사용자의 요구사항을 분석하여 최적의 AWS 서비스 구성을 추천해주세요.

응답 형식:
1. 추천 서비스 구성
2. 예상 월 비용
3. 아키텍처 설명
4. 비용 최적화 팁

구체적이고 실용적인 조언을 제공해주세요."""
                
                body = json.dumps({
                    "messages": [
                        {
                            "role": "user", 
                            "content": [
                                {"text": f"{system_prompt}\n\n{prompt}"}
                            ]
                        }
                    ],
                    "inferenceConfig": {
                        "max_new_tokens": 1000,
                        "temperature": 0.3
                    }
                })
                
                response = self.client.invoke_model(
                    modelId="amazon.nova-micro-v1:0",
                    body=body,
                    contentType="application/json"
                )
                
                result = json.loads(response['body'].read())
                ai_response = result['output']['message']['content'][0]['text']
                
                self.results[request_uuid] = {
                    'status': 'completed',
                    'result': ai_response
                }
                
            except Exception as e:
                self.results[request_uuid] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 백그라운드 스레드에서 실행
        thread = threading.Thread(target=run_analysis)
        thread.start()
        
        # 초기 상태 설정
        self.results[request_uuid] = {'status': 'processing'}
    
    def get_result(self, request_uuid):
        """결과 조회"""
        return self.results.get(request_uuid, {'status': 'not_found'})