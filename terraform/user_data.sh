#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "Starting user-data script"

yum update -y
yum install -y python3 python3-pip git

# 프론트엔드 설정
cd /home/ec2-user
echo "Setting up frontend"
mkdir -p frontend
cd frontend

cat > app.py << 'EOF'
from flask import Flask, render_template, request, jsonify
import uuid
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/estimate', methods=['POST'])
def estimate():
    data = request.json
    prompt = data.get('prompt')
    budget = data.get('budget')
    
    request_uuid = str(uuid.uuid4())
    
    try:
        response = requests.post('http://localhost:5001/process', json={
            'uuid': request_uuid,
            'prompt': prompt,
            'budget': budget
        })
    except Exception as e:
        print(f"Backend API call failed: {e}")
    
    return jsonify({'uuid': request_uuid})

@app.route('/poll/<request_uuid>')
def poll_result(request_uuid):
    try:
        response = requests.get(f'http://localhost:5001/result/{request_uuid}')
        return response.json()
    except Exception as e:
        print(f"Backend polling failed: {e}")
        return jsonify({'status': 'processing'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

mkdir -p templates
cat > templates/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>CloudOptimizer</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        #result { margin-top: 20px; padding: 20px; background: #e9ecef; border-radius: 5px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AWS 서비스 추천 플랫폼</h1>
        <form id="estimateForm">
            <div class="form-group">
                <label>서비스 설명:</label>
                <textarea id="prompt" rows="4" placeholder="원하는 서비스를 설명해주세요" required></textarea>
            </div>
            <div class="form-group">
                <label>월 예산 (USD):</label>
                <input type="number" id="budget" min="1" placeholder="100" required>
            </div>
            <button type="submit">추천 받기</button>
        </form>
        <div id="result">
            <h3>분석 중...</h3>
            <p id="status">잠시만 기다려주세요.</p>
        </div>
    </div>

    <script>
        document.getElementById('estimateForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const prompt = document.getElementById('prompt').value;
            const budget = document.getElementById('budget').value;
            
            document.getElementById('result').style.display = 'block';
            
            try {
                const response = await fetch('/estimate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, budget })
                });
                
                const data = await response.json();
                pollResult(data.uuid);
            } catch (error) {
                document.getElementById('status').textContent = '오류가 발생했습니다.';
            }
        });
        
        async function pollResult(uuid) {
            try {
                const response = await fetch('/poll/' + uuid);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    document.getElementById('status').innerHTML = '<strong>분석 완료!</strong><br><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } else if (data.status === 'failed') {
                    document.getElementById('status').innerHTML = '처리 실패';
                } else {
                    setTimeout(() => pollResult(uuid), 2000);
                }
            } catch (error) {
                document.getElementById('status').textContent = '폴링 오류';
            }
        }
    </script>
</body>
</html>
EOF

echo "Installing Python packages for frontend"
pip3 install flask requests
echo "Starting frontend server"
nohup python3 app.py > frontend.log 2>&1 &

# 백엔드 설정
cd /home/ec2-user
echo "Setting up backend"
git clone ${backend_repo} team02-aws-hackathon || echo "Repo clone failed"
cd team02-aws-hackathon || mkdir -p backend
git checkout ${backend_branch} || echo "Branch checkout failed"

# AWS Pricing API 사용 (서브모듈 불필요)
echo "Using AWS Pricing API directly"

cd backend || mkdir -p backend

# 백엔드가 없으면 생성
if [ ! -f app.py ]; then
cat > app.py << 'EOF'
from flask import Flask, request, jsonify
import json
import time
from threading import Thread

app = Flask(__name__)
results_store = {}

class AWSServiceEstimator:
    def __init__(self):
        self.service_costs = {
            'EC2': {'t2.micro': 8.5, 't2.small': 17, 't2.medium': 34},
            'RDS': {'db.t3.micro': 15, 'db.t3.small': 30},
            'S3': {'standard': 23, 'ia': 12.5}
        }
    
    def analyze_requirements(self, prompt, budget):
        services = []
        total_cost = 0
        
        if any(word in prompt.lower() for word in ['웹', 'web', 'api']):
            services.append({"name": "EC2", "type": "t2.micro", "quantity": 1, "reason": "웹서버"})
            total_cost += self.service_costs['EC2']['t2.micro']
            
            services.append({"name": "RDS", "type": "db.t3.micro", "quantity": 1, "reason": "데이터베이스"})
            total_cost += self.service_costs['RDS']['db.t3.micro']
        
        return {
            "services": services,
            "estimated_cost": total_cost,
            "feasible": total_cost <= float(budget)
        }

estimator = AWSServiceEstimator()

def process_request(request_uuid, prompt, budget):
    try:
        results_store[request_uuid] = {'status': 'processing'}
        time.sleep(3)
        
        analysis = estimator.analyze_requirements(prompt, budget)
        
        if analysis['feasible']:
            result = {
                'status': 'completed',
                'feasible': True,
                'services': analysis['services'],
                'total_cost': analysis['estimated_cost'],
                'budget': float(budget)
            }
        else:
            result = {
                'status': 'completed',
                'feasible': False,
                'message': f'예산 $' + str(budget) + '로는 요구사항을 충족할 수 없습니다.',
                'minimum_budget': analysis['estimated_cost']
            }
        
        results_store[request_uuid] = result
        
    except Exception as e:
        results_store[request_uuid] = {'status': 'failed', 'error': str(e)}

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    request_uuid = data.get('uuid')
    prompt = data.get('prompt')
    budget = data.get('budget')
    
    thread = Thread(target=process_request, args=(request_uuid, prompt, budget))
    thread.start()
    
    return jsonify({'uuid': request_uuid, 'status': 'processing'})

@app.route('/result/<request_uuid>')
def get_result(request_uuid):
    result = results_store.get(request_uuid, {'status': 'not_found'})
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
EOF
fi

echo "Installing Python packages for backend"
pip3 install flask boto3 pymongo

# DocumentDB 연결 설정
export MONGODB_URI="mongodb://admin:cloudoptimizer123@${docdb_endpoint}:27017/?ssl=true&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"

echo "Starting backend server"
nohup python3 app.py > backend.log 2>&1 &

echo "User-data script completed"