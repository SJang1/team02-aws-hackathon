# Team02 AWS Hackathon - Terraform Infrastructure

이 프로젝트는 AWS 리소스를 Terraform으로 관리하는 인프라 코드입니다.

## 구성 요소

- **VPC**: 10.0.0.0/16 CIDR 블록
- **Public Subnet**: 10.0.1.0/24 (웹 서버용)
- **Private Subnet**: 10.0.2.0/24 (데이터베이스용)
- **EC2 Instance**: Amazon Linux 2 웹 서버
- **S3 Bucket**: 파일 저장용
- **Security Groups**: 웹 트래픽 허용

## 사용 방법

### 1. 사전 준비
```bash
# Terraform 설치 확인
terraform version

# AWS CLI 설정 확인
aws configure list
```

### 2. 변수 설정
```bash
# terraform 폴더로 이동
cd terraform

# terraform.tfvars 파일 생성
cp terraform.tfvars.example terraform.tfvars

# 필요한 값들 수정
vi terraform.tfvars
```

### 3. Terraform 실행
```bash
# 초기화
terraform init

# 계획 확인
terraform plan

# 적용
terraform apply

# 리소스 정보 확인
terraform output
```

### 4. 정리
```bash
# 모든 리소스 삭제
terraform destroy
```

## 주요 출력값

- `web_instance_public_ip`: 웹 서버 공인 IP
- `web_instance_public_dns`: 웹 서버 공인 DNS
- `s3_bucket_name`: S3 버킷 이름

## 보안 고려사항

- EC2 키 페어를 미리 생성해야 합니다
- terraform.tfvars 파일은 Git에 커밋하지 마세요
- 프로덕션 환경에서는 더 엄격한 보안 그룹 규칙을 적용하세요