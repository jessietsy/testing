from flask import Flask, render_template, request, jsonify
from detector import detect_java_files
import os, zipfile

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok = True)



@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
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
        
        return jsonify({
            'build_system': detection['build_system'],
            'java_files': detection['java_files'],
            'entry_points': detection['entry_points']
        }   
        )
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
