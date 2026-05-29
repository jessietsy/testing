from flask import Flask, render_template, request, jsonify
from detector import detect_java_files
from docker_runner import run_and_measure
from ai_evaluator import evaluate
from database import create_tables, insert, get_all, get_by_id
from endpoint_detector import detect_endpoints
import os, zipfile

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok = True)



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/evaluate', methods=['POST'])
def evaluator():
    create_tables() # Initialise database and tables if they don't exist yet
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Invalid file type. File must be a zip'}), 400
    
    extract_path = os.path.join(UPLOAD_FOLDER, 'project')
    os.makedirs(extract_path, exist_ok = True)

    with zipfile.ZipFile(file, 'r') as myzip:
        myzip.extractall(extract_path)



    detection = detect_java_files(extract_path)
    if detection['errors']:
        return jsonify({'errors': detection['errors']}), 400
    
    # Detect endpoints and run load test
    endpoints = detect_endpoints(detection['project_root'])
    result = run_and_measure(detection['project_root'], detection['build_system'])
    if not result['build_success']:
        return jsonify({'errors': result['errors']}), 400

    
    # result = {
    #     'build_success': True,
    #     'run_success': True,
    #     'metrics': {},
    #     'errors': []
    # }

    # result['metrics'] = {
    #     'response_time_seconds': 0.1,
    #     'cpu_percent': 50.0,
    #     'memory_usage': 100.0,
    #     'memory_percent': 25.0
    # }
    print(result['metrics'])

    # Evaluation using AI model
    eval_result = evaluate(result['metrics'], detection['build_system'])
    if not eval_result['success']:
        return jsonify({'error': 'Evaluation failed', 'details': eval_result['errors']}), 400
    
    # Save result to database
    eval_id = insert(file.filename, detection['build_system'], result['metrics'], eval_result['evaluation'], eval_result['evaluation'].get('overall_rating'), result['errors'])
    return jsonify({'evaluation_id': eval_id, 'metrics': result['metrics'], 'evaluation': eval_result['evaluation'], 'run_errors': result['errors']})


@app.route('/history')
def history():
    evaluations = get_all()
    return jsonify({'evaluations': evaluations})



if __name__ == '__main__':
    app.run(debug=True)
