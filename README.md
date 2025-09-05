# CloudOptimizer - AWS 서비스 추천 플랫폼

AI 기반으로 사용자의 요구사항과 예산에 맞는 최적의 AWS 서비스 구성을 추천하는 플랫폼입니다.

## 아키텍처

```
사용자 → ALB → EC2 (Frontend + Backend) → Bedrock → AWS Pricing API
```

## 프로젝트 구조

```
├── front/                 # 프론트엔드 (Flask)
│   ├── app.py
│   ├── templates/
│   │   └── index.html
│   └── requirements.txt
├── backend/               # 백엔드 (Flask + Bedrock)
│   ├── app.py
│   └── requirements.txt
├── terraform/             # 인프라 구성
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── user_data.sh
│   └── terraform.tfvars.example
└── README.md
```

## 배포 방법

### 1. 사전 준비

1. AWS CLI 설정
```bash
aws configure
```

2. EC2 Key Pair 생성
```bash
aws ec2 create-key-pair --key-name cloudoptimizer-key --query 'KeyMaterial' --output text > cloudoptimizer-key.pem
chmod 400 cloudoptimizer-key.pem
```

### 2. Terraform 배포

1. 변수 파일 설정
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars 파일을 편집하여 key_name 등 설정
```

2. Terraform 초기화 및 배포
```bash
terraform init
terraform plan
terraform apply
```

### 3. 접속

배포 완료 후 출력되는 Load Balancer URL로 접속:
```
http://your-alb-dns-name
```

## 주요 기능

1. **사용자 입력**: 서비스 유형, 사용자 수, 성능 요구사항, 예산 입력
2. **UUID 생성**: 각 요청에 대한 고유 식별자 생성
3. **Bedrock 분석**: AI를 통한 서비스 요구사항 분석
4. **비용 계산**: AWS Pricing API를 통한 실시간 비용 계산
5. **서비스 최적화**: 예산 내에서 최적의 서비스 조합 제안
6. **Polling**: 비동기 처리 결과를 실시간으로 확인

## API 엔드포인트

### 프론트엔드 (포트 5000)
- `GET /`: 메인 페이지
- `POST /estimate`: 추천 요청
- `GET /poll/<uuid>`: 결과 폴링

### 백엔드 (포트 5001)
- `POST /process`: 요청 처리 시작
- `GET /result/<uuid>`: 처리 결과 조회
- `GET /health`: 헬스체크

## 환경 변수

- `AWS_REGION`: AWS 리전 (기본값: ap-northeast-2)
- `AWS_ACCESS_KEY_ID`: AWS 액세스 키
- `AWS_SECRET_ACCESS_KEY`: AWS 시크릿 키

## 리소스 정리

```bash
terraform destroy
```

## 주의사항

1. Bedrock 모델 사용 권한이 필요합니다
2. EC2 인스턴스에 적절한 IAM 역할이 할당되어야 합니다
3. 비용 최적화를 위해 t3.micro 인스턴스를 사용합니다