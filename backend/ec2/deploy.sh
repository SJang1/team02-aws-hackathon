#!/bin/bash

# EC2 배포 스크립트
echo "AWS Service Recommender 배포 시작..."

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
export AWS_DEFAULT_REGION=us-east-1

# DynamoDB 테이블 생성 (존재하지 않는 경우)
aws dynamodb create-table \
    --table-name aws-recommendations \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1 2>/dev/null || echo "테이블이 이미 존재합니다."

# 서버 시작
echo "서버 시작 중..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload