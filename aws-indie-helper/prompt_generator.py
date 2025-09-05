#!/usr/bin/env python3
"""
AWS Indie Helper - AI Prompt Generator
사용자 입력을 받아 Bedrock AI용 프롬프트로 변환
"""

import http.server
import socketserver
import json
import urllib.parse
from typing import Dict

class PromptGeneratorHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/generate-prompt':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                user_input = json.loads(post_data.decode('utf-8'))
                prompt = self.generate_bedrock_prompt(user_input)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response = json.dumps({
                    "generated_prompt": prompt,
                    "user_selections": user_input
                }, indent=2, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
                
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def generate_bedrock_prompt(self, user_input: Dict) -> str:
        """사용자 입력을 Bedrock AI용 프롬프트로 변환"""
        
        # 기본 프롬프트 템플릿
        prompt = """당신은 AWS 클라우드 아키텍처 전문가입니다. 다음 요구사항에 맞는 최적의 AWS 서비스 조합을 추천해주세요.

## 프로젝트 정보
"""
        
        # 프로젝트 기본 정보
        prompt += f"- 프로젝트 유형: {self.get_project_type_korean(user_input.get('project_type', ''))}\n"
        prompt += f"- 예상 사용자 수: {user_input.get('expected_users', 'N/A')}명\n"
        prompt += f"- 월 예산: ${user_input.get('budget', 'N/A')}\n"
        prompt += f"- 선호 리전: {self.get_region_korean(user_input.get('region', ''))}\n"
        
        # 기술 스택
        if user_input.get('tech_stack'):
            prompt += f"- 기술 스택: {', '.join(user_input['tech_stack'])}\n"
        
        # 특수 요구사항
        requirements = []
        if user_input.get('needs_database'):
            requirements.append("데이터베이스 필요")
        if user_input.get('needs_realtime'):
            requirements.append("실시간 기능 필요")
        if user_input.get('needs_cdn'):
            requirements.append("CDN 필요")
        if user_input.get('needs_auth'):
            requirements.append("사용자 인증 필요")
        if user_input.get('needs_monitoring'):
            requirements.append("모니터링 필요")
        
        if requirements:
            prompt += f"- 특수 요구사항: {', '.join(requirements)}\n"
        
        # 자연어 추가 요청사항
        if user_input.get('additional_requirements'):
            prompt += f"\n## 추가 요청사항\n{user_input['additional_requirements']}\n"
        
        # 응답 형식 지정
        prompt += """
## 요청사항
다음 형식으로 응답해주세요:

1. **추천 AWS 서비스 목록**
   - 각 서비스별 인스턴스 타입과 예상 월 비용
   - 선택 이유 간단 설명

2. **아키텍처 다이어그램 설명**
   - 서비스 간 연결 관계 설명

3. **예상 총 월 비용**
   - 서비스별 비용 breakdown

4. **Terraform 코드**
   - 추천 서비스들의 기본 Terraform 설정

5. **추가 고려사항**
   - 보안, 확장성, 모니터링 관련 권장사항

응답은 한국어로 작성해주세요.
"""
        
        return prompt
    
    def get_project_type_korean(self, project_type: str) -> str:
        types = {
            'web_service': '웹 서비스',
            'mobile_app': '모바일 앱',
            'game': '게임',
            'api': 'API 서비스',
            'ml_ai': 'ML/AI 서비스',
            'iot': 'IoT 서비스',
            'blog': '블로그/CMS',
            'ecommerce': '이커머스'
        }
        return types.get(project_type, project_type)
    
    def get_region_korean(self, region: str) -> str:
        regions = {
            'us-east-1': '미국 동부 (버지니아)',
            'us-west-2': '미국 서부 (오레곤)',
            'ap-northeast-2': '아시아 태평양 (서울)',
            'ap-northeast-1': '아시아 태평양 (도쿄)',
            'eu-west-1': '유럽 (아일랜드)',
            'eu-central-1': '유럽 (프랑크푸르트)'
        }
        return regions.get(region, region)

if __name__ == "__main__":
    PORT = 8000
    with socketserver.TCPServer(("", PORT), PromptGeneratorHandler) as httpd:
        print(f"🤖 AI 프롬프트 생성기 시작: http://localhost:{PORT}")
        print("종료하려면 Ctrl+C를 누르세요")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버 종료")
            httpd.shutdown()