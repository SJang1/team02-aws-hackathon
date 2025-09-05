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
    
    # UUID 생성 및 백엔드로 요청
    request_uuid = str(uuid.uuid4())
    
    # 백엔드 API 호출
    try:
        response = requests.post('http://localhost:5001/process', json={
            'uuid': request_uuid,
            'prompt': prompt,
            'budget': budget
        })
    except Exception as e:
        print(f"Backend API 호출 실패: {e}")
    
    print(f"Generated prompt for UUID {request_uuid}:")
    print(prompt)
    
    return jsonify({'uuid': request_uuid})

@app.route('/poll/<request_uuid>')
def poll_result(request_uuid):
    # 백엔드에서 결과 폴링
    try:
        response = requests.get(f'http://localhost:5001/result/{request_uuid}')
        return response.json()
    except Exception as e:
        print(f"Backend polling 실패: {e}")
        return jsonify({'status': 'processing'})

if __name__ == '__main__':
    app.run(debug=True)