#!/bin/bash

sudo yum update -y
sudo yum install -y python3 python3-pip
pip3 install flask flask-cors requests boto3

# 백엔드 서버 (imsi_new.py) 실행
echo "Starting backend server (imsi_new.py) on port 5000..."
cd /home/ec2-user
python3 imsi_new.py &
BACKEND_PID=$!

# 프론트엔드 서버 (front/app.py) 실행
echo "Starting frontend server on port 8080..."
cd /home/ec2-user/front
python3 app.py &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Servers started successfully!"
echo "Frontend: http://localhost:8080"
echo "Backend: http://localhost:5000"
