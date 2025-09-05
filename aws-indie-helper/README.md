# AWS AI Helper

Amazon Bedrock 기반 AI를 위한 맞춤형 AWS 서비스 추천 프롬프트 생성기

## 기능
- 사용자 요구사항 수집 UI
- 프로젝트 유형, 기술 스택, 예상 사용자 수 등 선택
- 자연어 추가 요구사항 입력
- Amazon Bedrock AI용 최적화된 프롬프트 생성
- 프롬프트 복사 기능

## 사용 예시
1. 프로젝트 유형 선택 (웹서비스, 게임, API 등)
2. 기술 스택 선택 (Python, React, Unity 등)
3. 서비스 요구사항 체크 (데이터베이스, CDN, 인증 등)
4. 자연어로 추가 요구사항 입력
5. AI 프롬프트 생성 및 복사
6. Amazon Bedrock에 프롬프트 입력하여 AWS 아키텍처 추천 받기

## 기술 스택
- Backend: Python 3 (순수 HTTP 서버)
- Frontend: HTML/CSS/JavaScript
- AI Integration: Amazon Bedrock 호환 프롬프트

## 실행 방법
```bash
./start.sh
```

## 파일 구조
- `prompt_generator.py`: AI 프롬프트 생성 서버
- `ai_interface.html`: 사용자 입력 인터페이스
- `start.sh`: 실행 스크립트