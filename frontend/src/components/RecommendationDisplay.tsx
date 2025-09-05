import React from 'react';

interface Recommendation {
  services: string[];
  architecture: string;
  estimatedCost: number;
}

interface RecommendationDisplayProps {
  recommendation: Recommendation | null;
}

const RecommendationDisplay: React.FC<RecommendationDisplayProps> = ({ recommendation }) => {
  if (!recommendation) return null;

  return (
    <div style={{backgroundColor: 'white', padding: '24px', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', marginTop: '24px'}}>
      <h3 style={{fontSize: '20px', fontWeight: 'bold', marginBottom: '16px', color: '#1f2937'}}>추천 결과</h3>
      
      <div style={{marginBottom: '16px'}}>
        <h4 style={{fontWeight: '600', color: '#374151', marginBottom: '8px'}}>추천 AWS 서비스</h4>
        <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px'}}>
          {recommendation.services.map((service, index) => (
            <span
              key={index}
              style={{
                backgroundColor: '#dbeafe',
                color: '#1e40af',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '14px'
              }}
            >
              {service}
            </span>
          ))}
        </div>
      </div>

      <div style={{marginBottom: '16px'}}>
        <h4 style={{fontWeight: '600', color: '#374151', marginBottom: '8px'}}>아키텍처 설명</h4>
        <p style={{color: '#6b7280', whiteSpace: 'pre-line'}}>{recommendation.architecture}</p>
      </div>

      <div style={{backgroundColor: '#f0fdf4', padding: '16px', borderRadius: '6px'}}>
        <h4 style={{fontWeight: '600', color: '#166534', marginBottom: '4px'}}>예상 월 비용</h4>
        <p style={{fontSize: '24px', fontWeight: 'bold', color: '#16a34a'}}>${recommendation.estimatedCost}</p>
      </div>
    </div>
  );
};

export default RecommendationDisplay;