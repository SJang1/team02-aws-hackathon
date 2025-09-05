#!/bin/bash

sudo yum update -y
sudo yum install -y python3 python3-pip mysql

# Install compatible versions for older OpenSSL
pip3 install flask flask-cors
pip3 install "urllib3<2.0" "requests<2.29.0" "boto3" "PyMySQL" "cryptography"

echo "🚀 Starting ClOps servers with RDS auto-discovery..."

# 백엔드 서버 (RDS 자동 연결) 실행
echo "Starting backend server with RDS auto-discovery on port 5000..."
cd /home/ec2-user
python3 imsi_new.py &
BACKEND_PID=$!

# 프론트엔드 서버 실행
echo "Starting frontend server on port 8080..."
cd /home/ec2-user/front
python3 app.py &
FRONTEND_PID=$!

echo "✅ Servers started successfully!"
echo "   Backend PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo "   Frontend: http://localhost:8080"
echo "   Backend: http://localhost:5000"
echo "   Logs: backend.log, frontend.log"
echo ""
echo "🔍 RDS connection will be auto-discovered from AWS API"
echo "📋 Check logs with: tail -f backend.log frontend.log"