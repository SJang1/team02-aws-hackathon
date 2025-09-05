import React, { useState } from 'react';
import ServiceRequestForm from './components/ServiceRequestForm';
import RecommendationDisplay from './components/RecommendationDisplay';

interface Recommendation {
  services: string[];
  architecture: string;
  estimatedCost: number;
}

function App() {
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (description: string, budget: number) => {
    setLoading(true);
    try {
      const response = await fetch('https://gfctablne7.execute-api.us-east-1.amazonaws.com/dev/recommend', {
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
