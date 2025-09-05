# AWS 서비스 추천 시스템 아키텍처

## 시스템 구조

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React Frontend │────│   EC2 Instance   │────│ Amazon Bedrock  │
│   (기존 코드)     │    │   FastAPI Server │    │   (AI 추천)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │ HTTPS 요청              │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │  AWS Pricing API │    │   DynamoDB      │
│   (CDN)         │    │  (실시간 비용)    │    │   (결과 저장)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 데이터 플로우

1. **사용자 입력**: 프론트엔드에서 서비스 설명과 예산 입력
2. **가격 수집**: EC2 서버가 AWS Pricing API에서 실시간 가격 정보 수집
3. **AI 추천**: 가격 정보와 함께 Bedrock에 추천 요청
4. **비용 계산**: Bedrock 응답을 바탕으로 정확한 비용 계산
5. **최적화**: 예산 내에서 최적의 서비스 조합 선택
6. **결과 반환**: 상세한 추천 결과를 프론트엔드에 전달

## 주요 기능

### EC2 서버 (FastAPI)
- AWS Pricing API 통합
- Bedrock AI 모델 호출
- 실시간 비용 계산
- 예산 최적화 로직
- DynamoDB 데이터 저장

### 프론트엔드 (React)
- 사용자 입력 폼
- 추천 결과 시각화
- 비용 분석 표시
- 예산 사용률 표시

## 배포 방법

### EC2 배포
```bash
cd backend/ec2
chmod +x deploy.sh
./deploy.sh
```

### Docker 배포
```bash
cd backend/ec2
docker-compose up -d
```

## 환경 변수 설정

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## API 엔드포인트

- `POST /api/recommend`: 서비스 추천 요청
- `GET /health`: 헬스 체크
- `GET /`: API 정보

## 기술 스택

- **Backend**: FastAPI, Python 3.9+
- **Frontend**: React, TypeScript
- **AI**: Amazon Bedrock (Claude 3)
- **Database**: DynamoDB
- **Pricing**: AWS Pricing API
- **Deployment**: EC2, Docker