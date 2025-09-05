import streamlit as st
import requests
import json

st.set_page_config(
    page_title="AWS Indie Helper",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 AWS Indie Helper")
st.markdown("인디 게임/웹 서비스 개발자를 위한 AWS 서비스 추천 도구")

# 사이드바 입력
with st.sidebar:
    st.header("프로젝트 정보")
    
    project_type = st.selectbox(
        "프로젝트 유형",
        ["web_service", "game"],
        format_func=lambda x: "웹 서비스" if x == "web_service" else "게임"
    )
    
    expected_users = st.number_input(
        "예상 사용자 수",
        min_value=1,
        max_value=1000000,
        value=100,
        step=100
    )
    
    budget = st.number_input(
        "월 예산 (USD)",
        min_value=10.0,
        max_value=10000.0,
        value=100.0,
        step=10.0
    )
    
    region = st.selectbox(
        "AWS 리전",
        ["us-east-1", "ap-northeast-2", "eu-west-1"],
        format_func=lambda x: {
            "us-east-1": "미국 동부 (버지니아)",
            "ap-northeast-2": "아시아 태평양 (서울)",
            "eu-west-1": "유럽 (아일랜드)"
        }[x]
    )

# 메인 컨텐츠
col1, col2 = st.columns([2, 1])

with col1:
    if st.button("서비스 추천 받기", type="primary"):
        with st.spinner("추천 서비스를 분석 중..."):
            try:
                response = requests.post(
                    "http://localhost:8000/api/recommend",
                    json={
                        "project_type": project_type,
                        "expected_users": expected_users,
                        "budget": budget,
                        "region": region
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    st.success(f"총 예상 비용: ${data['total_monthly_cost']:.2f}/월")
                    
                    st.subheader("추천 서비스")
                    for rec in data["recommendations"]:
                        with st.expander(f"{rec['service_name']} - ${rec['monthly_cost']}/월"):
                            st.write(f"**인스턴스 타입:** {rec['instance_type']}")
                            st.write(f"**설명:** {rec['description']}")
                    
                    st.subheader("Terraform 설정")
                    st.code(data["terraform_config"], language="hcl")
                    
                else:
                    st.error("서비스 추천 중 오류가 발생했습니다.")
                    
            except requests.exceptions.ConnectionError:
                st.error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.")

with col2:
    st.subheader("💡 팁")
    
    if project_type == "web_service":
        st.info("""
        **웹 서비스 권장사항:**
        - 시작은 t3.micro로
        - RDS 대신 DynamoDB 고려
        - CloudFront로 성능 향상
        - Auto Scaling 설정 권장
        """)
    else:
        st.info("""
        **게임 서비스 권장사항:**
        - GameLift로 멀티플레이어 지원
        - DynamoDB로 빠른 데이터 액세스
        - ElastiCache로 세션 관리
        - CloudWatch로 모니터링
        """)
    
    st.subheader("📊 비용 절약 팁")
    st.markdown("""
    - Reserved Instance 활용
    - Spot Instance 고려
    - S3 Intelligent Tiering
    - CloudWatch 알람 설정
    """)

# 푸터
st.markdown("---")
st.markdown("Made with ❤️ for indie developers")