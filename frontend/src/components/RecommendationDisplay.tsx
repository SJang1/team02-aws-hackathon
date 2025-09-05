import React from 'react';

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

interface RecommendationDisplayProps {
  recommendation: Recommendation | null;
}

const RecommendationDisplay: React.FC<RecommendationDisplayProps> = ({ recommendation }) => {
  if (!recommendation) return null;

  return (
    <div style={{backgroundColor: 'white', padding: '24px', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', marginTop: '24px'}}>
      <h3 style={{fontSize: '20px', fontWeight: 'bold', marginBottom: '16px', color: '#1f2937'}}>추천 결과</h3>
      
      <div style={{marginBottom: '20px'}}>
        <h4 style={{fontWeight: '600', color: '#374151', marginBottom: '12px'}}>추천 AWS 서비스</h4>
        <div style={{display: 'grid', gap: '12px'}}>
          {recommendation.services.map((service, index) => (
            <div key={index} style={{
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '16px',
              backgroundColor: '#f9fafb'
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                <span style={{fontWeight: '600', color: '#1f2937'}}>{service.service_name}</span>
                <span style={{fontWeight: 'bold', color: '#059669'}}>${service.monthly_cost.toFixed(2)}/월</span>
              </div>
              <div style={{fontSize: '14px', color: '#6b7280', marginBottom: '4px'}}>
                {service.instance_type} - {service.description}
              </div>
              {service.reason && (
                <div style={{fontSize: '12px', color: '#9ca3af', fontStyle: 'italic'}}>
                  선택 이유: {service.reason}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{marginBottom: '20px'}}>
        <h4 style={{fontWeight: '600', color: '#374151', marginBottom: '8px'}}>아키텍처 설명</h4>
        <p style={{color: '#6b7280', whiteSpace: 'pre-line', lineHeight: '1.6'}}>{recommendation.architecture}</p>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px'}}>
        <div style={{backgroundColor: '#f0fdf4', padding: '16px', borderRadius: '6px'}}>
          <h4 style={{fontWeight: '600', color: '#166534', marginBottom: '4px'}}>총 월 비용</h4>
          <p style={{fontSize: '24px', fontWeight: 'bold', color: '#16a34a'}}>${recommendation.total_cost.toFixed(2)}</p>
        </div>
        
        <div style={{backgroundColor: '#eff6ff', padding: '16px', borderRadius: '6px'}}>
          <h4 style={{fontWeight: '600', color: '#1e40af', marginBottom: '4px'}}>예산 사용률</h4>
          <p style={{fontSize: '24px', fontWeight: 'bold', color: '#2563eb'}}>{recommendation.budget_utilization.toFixed(1)}%</p>
        </div>
      </div>
    </div>
  );
};

export default RecommendationDisplay;