import React, { useState } from 'react';
import ServiceRequestForm from './components/ServiceRequestForm';
import RecommendationDisplay from './components/RecommendationDisplay';

interface ServiceDetail {
  service_name: string;
  instance_type: string;
  monthly_cost: number;
  description: string;
  reason?: string;
  cost_per_hour?: number;
}

interface Recommendation {
  services: ServiceDetail[];
  architecture: string;
  total_cost: number;
  budget_utilization: number;
  cost_breakdown?: {
    total_monthly: number;
    total_yearly: number;
    by_service: Record<string, any>;
  };
}

function App() {
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (description: string, budget: number) => {
    setLoading(true);
    try {
      // EC2 서버 엔드포인트로 변경 (배포 후 실제 IP/도메인으로 수정 필요)
      const response = await fetch('http://localhost:8000/api/recommend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ description, budget })
      });
      
      if (!response.ok) {
        throw new Error('API 호출 실패');
      }
      
      const data = await response.json();
      setRecommendation(data);
    } catch (error) {
      console.error('Error:', error);
      alert('추천 생성 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{minHeight: '100vh', padding: '32px 0'}}>
      <div style={{maxWidth: '896px', margin: '0 auto', padding: '0 16px'}}>
        <h1 style={{fontSize: '30px', fontWeight: 'bold', textAlign: 'center', marginBottom: '32px', color: '#1f2937'}}>
          AWS 서비스 추천 시스템
        </h1>
        
        <ServiceRequestForm onSubmit={handleSubmit} loading={loading} />
        <RecommendationDisplay recommendation={recommendation} />
      </div>
    </div>
  );
}

export default App;
