from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

BACKEND_URL = 'http://localhost:5000'  # imsi.py 서버 주소

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/optimize', methods=['POST'])
def optimize():
    data = request.json
    
    # imsi.py 백엔드로 요청 전달
    try:
        response = requests.post(f'{BACKEND_URL}/optimize', 
                               json=data, 
                               timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<request_uuid>')
def get_status(request_uuid):
    # imsi.py 백엔드에서 결과 조회
    try:
        response = requests.get(f'{BACKEND_URL}/status/{request_uuid}', 
                              timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)