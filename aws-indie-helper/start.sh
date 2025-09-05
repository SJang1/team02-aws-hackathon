#!/bin/bash

echo "🚀 AWS Indie Helper 시작 (의존성 없는 버전)"

# 백엔드 실행
echo "백엔드 서버 시작 중..."
python3 simple_server.py &
BACKEND_PID=$!

# 잠시 대기
sleep 2

# 프론트엔드 열기
echo "프론트엔드 열기..."
if command -v xdg-open > /dev/null; then
    xdg-open simple_frontend.html
elif command -v open > /dev/null; then
    open simple_frontend.html
else
    echo "브라우저에서 simple_frontend.html 파일을 열어주세요"
fi

echo "✅ 서버 실행 완료!"
echo "📱 프론트엔드: simple_frontend.html 파일을 브라우저에서 열기"
echo "🔧 백엔드 API: http://localhost:8000"
echo ""
echo "종료하려면 Ctrl+C를 누르세요"

# 종료 시그널 처리
trap "kill $BACKEND_PID; exit" INT

wait