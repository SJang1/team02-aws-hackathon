#!/bin/bash

echo "🚀 AWS Indie Helper 시작"

# 백엔드 실행
echo "백엔드 서버 시작 중..."
cd backend
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# 잠시 대기
sleep 3

# 프론트엔드 실행
echo "프론트엔드 시작 중..."
cd ../frontend
streamlit run app.py --server.port 8501 &
FRONTEND_PID=$!

echo "✅ 서버 실행 완료!"
echo "📱 프론트엔드: http://localhost:8501"
echo "🔧 백엔드 API: http://localhost:8000"
echo ""
echo "종료하려면 Ctrl+C를 누르세요"

# 종료 시그널 처리
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

wait