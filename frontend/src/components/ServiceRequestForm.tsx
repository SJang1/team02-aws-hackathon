import React, { useState } from 'react';

interface ServiceRequestFormProps {
  onSubmit: (description: string, budget: number) => void;
  loading: boolean;
}

const ServiceRequestForm: React.FC<ServiceRequestFormProps> = ({ onSubmit, loading }) => {
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState<number>(0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim() && budget > 0) {
      onSubmit(description, budget);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{backgroundColor: 'white', padding: '24px', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)'}}>
      <h2 style={{fontSize: '24px', fontWeight: 'bold', marginBottom: '16px', color: '#1f2937'}}>AWS 서비스 추천 요청</h2>
      
      <div style={{marginBottom: '16px'}}>
        <label style={{display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px'}}>
          서비스 설명
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="구축하고자 하는 서비스를 설명해주세요..."
          style={{width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '14px'}}
          rows={4}
          required
        />
      </div>

      <div style={{marginBottom: '24px'}}>
        <label style={{display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px'}}>
          예산 (USD)
        </label>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          placeholder="월 예산을 입력하세요"
          style={{width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '14px'}}
          min="1"
          required
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        style={{
          width: '100%',
          backgroundColor: loading ? '#9ca3af' : '#2563eb',
          color: 'white',
          padding: '12px 16px',
          borderRadius: '6px',
          border: 'none',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '16px'
        }}
      >
        {loading ? '추천 생성 중...' : 'AWS 서비스 추천 받기'}
      </button>
    </form>
  );
};

export default ServiceRequestForm;