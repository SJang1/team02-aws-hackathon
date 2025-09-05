#!/bin/bash

echo "🤖 AWS AI Helper 시작"

# AI 프롬프트 생성기 실행
echo "AI 프롬프트 생성기 시작 중..."
python3 prompt_generator.py &
BACKEND_PID=$!

# 잠시 대기
sleep 2

# 프론트엔드 열기
echo "AI 인터페이스 열기..."
if command -v xdg-open > /dev/null; then
    xdg-open ai_interface.html
elif command -v open > /dev/null; then
    open ai_interface.html
else
    echo "브라우저에서 ai_interface.html 파일을 열어주세요"
fi

echo "✅ 서버 실행 완료!"
echo "🤖 AI 인터페이스: ai_interface.html 파일을 브라우저에서 열기"
echo "🔧 프롬프트 생성 API: http://localhost:8000"
echo ""
echo "종료하려면 Ctrl+C를 누르세요"

# 종료 시그널 처리
trap "kill $BACKEND_PID; exit" INT

wait