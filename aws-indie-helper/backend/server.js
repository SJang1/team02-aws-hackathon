const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// 서비스 추천 엔드포인트
app.post('/api/recommend', (req, res) => {
  const { projectType, expectedUsers, budget } = req.body;
  
  const recommendations = getRecommendations(projectType, expectedUsers, budget);
  res.json(recommendations);
});

// 비용 계산 엔드포인트
app.post('/api/calculate-cost', (req, res) => {
  const { services, usage } = req.body;
  
  const cost = calculateCost(services, usage);
  res.json({ estimatedMonthlyCost: cost });
});

function getRecommendations(type, users, budget) {
  const baseServices = {
    webService: {
      compute: users < 1000 ? 't3.micro' : 't3.small',
      database: 'RDS MySQL t3.micro',
      storage: 'S3 Standard',
      cdn: 'CloudFront',
      monitoring: 'CloudWatch'
    },
    game: {
      compute: 't3.small',
      database: 'DynamoDB',
      storage: 'S3 Standard + GameLift',
      cdn: 'CloudFront',
      monitoring: 'CloudWatch + X-Ray'
    }
  };
  
  return baseServices[type] || baseServices.webService;
}

function calculateCost(services, usage) {
  // 간단한 비용 계산 로직
  const pricing = {
    't3.micro': 8.5,
    't3.small': 17,
    'rds-micro': 15,
    's3-standard': 0.023,
    'cloudfront': 0.085
  };
  
  let total = 0;
  Object.entries(services).forEach(([service, config]) => {
    total += pricing[config] || 10;
  });
  
  return Math.round(total * (usage / 100));
}

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});