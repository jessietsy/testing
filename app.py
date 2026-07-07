from flask import Flask, render_template, request, jsonify
from file_detector import detect_java_files
from docker_runner import run_and_measure
from ai_evaluator import evaluate
from database import create_tables, insert, get_all, get_by_id
from endpoint_detector import detect_endpoints, detect_port
import os, zipfile, shutil

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

    try: 
        with zipfile.ZipFile(file, 'r') as myzip:
            myzip.extractall(extract_path)



        detection = detect_java_files(extract_path)
        print(detection)

        if detection['errors']:
            return jsonify({'errors': detection['errors']}), 400
        
        # Detect endpoints and run load test
        port = detect_port(detection['project_root'])
        static_endpoints = detect_endpoints(detection['project_root'])
        print(f'Detected port: {port}')
        print(f'[For Debugging] Statically detected endpoints: {static_endpoints}')

        result = run_and_measure(detection['project_root'], detection['build_system'], port=port) 
        print(result)
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
        # result = {'build_success': True, 'run_success': True, 'metrics': {'avg_response_time_ms': 0, 'min_response_time_ms': 16.01, 'max_response_time_ms': 612.07, 'p95_response_time_ms': 0, 'requests_per_second': 0, 'cpu_peak_percent': 30.03, 'cpu_average_percent': 8.45, 'memory_peak_mb': 211.12, 'memory_average_mb': 207.26, 'total_requests': 19, 'failed_requests': 19, 'failure_rate_percent': 100.0, 'concurrent_users': 10}, 'errors': []}
        # print(result)

        scores = result['metrics'].get('scores', {})

        # Evaluation using AI model
        eval_result = evaluate(result['metrics'], detection['build_system'], scores)
        # print(eval_result)
        # eval_result = {'success': True, 'evaluation': {'overall_rating': 'Poor', 'summary': 'The API received an overall score of 82.9/100 (Grade B), however, this aggregate score masks a critical systemic issue. The system exhibits an extremely high overall failure rate of 86.21%, rendering most core functionalities non-operational and severely impacting the user experience.', 'time_behaviour': {'rating': 'Fair', 'findings': ['Average response times are generally good for most endpoints, with GET /api/product/{id} at 43.92ms and DELETE /api/product/{id} at 43.08ms. Even the file operation GET /api/product/{productId}/image has a reasonable average of 106.41ms.', 'However, P95 response times reveal significant inconsistency and slowness for certain operations, particularly for PUT /api/product/{id} which reached 910ms. Other high P95s include GET /api/product/{productId}/image at 530ms and POST /api/product at 420ms, indicating potential bottlenecks or long-running failures.'], 'recommendations': ['Investigate the root causes of high P95 response times, especially for PUT, POST, and image retrieval operations, as these suggest potential inefficiencies even in the failure path.', 'Optimize database queries, business logic, or consider caching mechanisms to reduce latency and improve consistency for all operations once the underlying failure issues are resolved.']}, 'resource_utilisation': {'rating': 'Good', 'findings': ['Resource utilization under a load of 10 users is notably low, with peak CPU at 25.62% and average CPU at 8.86%.', 'Memory usage is stable and low, peaking at 215.34 MB and averaging 212.62 MB.', "It's crucial to understand that these low utilization figures are likely a direct consequence of the widespread request failures; the system is not successfully processing most requests and therefore is not adequately stressed."], 'recommendations': ["After resolving the critical failure rates, re-evaluate resource utilization under a successful, sustained load to accurately gauge the system's true performance and capacity capabilities."]}, 'capacity': {'rating': 'Poor', 'findings': ['The system demonstrates severe capacity and reliability issues, evidenced by an alarming overall failure rate of 86.21% across 174 total requests.', 'A critical finding is that 6 out of 7 endpoints (GET /api/product/{id}, POST /api/product, GET /api/product/{productId}/image, PUT /api/product/{id}, DELETE /api/product/{id}, GET /api/products/search) exhibit a 100.0% failure rate, indicating a fundamental breakdown in functionality for nearly all key operations.', 'Only GET /api/products successfully processes requests with a 0.0% failure rate.'], 'recommendations': ['Initiate an immediate and thorough investigation into the root causes of the 100% failure rates across almost all endpoints. This must be the top priority.', 'Focus debugging efforts on server-side error logs, database connectivity, API contract validation (request payload/parameters), and authentication/authorization mechanisms.', 'Implement robust error handling and more informative error responses to expedite future debugging and issue resolution.']}, 'endpoint_findings': [{'endpoint': 'GET /api/product/{id}', 'score': 71.8, 'issue': 'Complete failure (100.0% failure rate) to retrieve individual product details.', 'recommendation': 'Examine server-side logic for ID parsing, database queries for single-item retrieval, and ensure correct data is being returned, if any.'}, {'endpoint': 'POST /api/product', 'score': 69.5, 'issue': 'Complete failure (100.0% failure rate) to create new products.', 'recommendation': 'Debug the product creation workflow, including request body validation, database insertion logic, and any associated business rules or transaction management.'}, {'endpoint': 'GET /api/product/{productId}/image', 'score': 75.0, 'issue': 'Complete failure (100.0% failure rate) to retrieve product images.', 'recommendation': 'Verify file storage access permissions, image path resolution, and the logic responsible for serving image content. Ensure the `productId` used for image retrieval corresponds to valid and accessible product data.'}, {'endpoint': 'PUT /api/product/{id}', 'score': 61.6, 'issue': 'Complete failure (100.0% failure rate) to update existing products, coupled with a critically high P95 response time of 910ms.', 'recommendation': "Prioritize debugging of the update operation's server-side logic, data validation, and database transaction integrity. Investigate why requests are taking so long to fail, suggesting potential deadlocks, timeouts, or unhandled exceptions."}, {'endpoint': 'DELETE /api/product/{id}', 'score': 71.5, 'issue': 'Complete failure (100.0% failure rate) to delete products.', 'recommendation': 'Review the deletion logic, including any foreign key constraints, cascading deletes, and ensure the authenticated user has appropriate permissions to perform deletions.'}, {'endpoint': 'GET /api/products/search', 'score': 75.0, 'issue': 'Complete failure (100.0% failure rate) for the product search functionality.', 'recommendation': 'Debug the search query parsing, indexing mechanisms (if applicable), and database search logic. Ensure search parameters are correctly handled and filtered, and that the search engine is operational.'}], 'priority_issues': ['The overwhelming 100% failure rate across critical write, read, update, and delete operations (e.g., POST /api/product, PUT /api/product/{id}, GET /api/product/{id}, DELETE /api/product/{id}), rendering the core API virtually unusable.', 'The PUT /api/product/{id} endpoint has the lowest score (61.6) and a critically high P95 response time (910ms) despite its 100% failure rate, indicating severe performance and functional issues.']}, 'raw_response': '{\n    "overall_rating": "Poor",\n    "summary": "The API received an overall score of 82.9/100 (Grade B), however, this aggregate score masks a critical systemic issue. The system exhibits an extremely high overall failure rate of 86.21%, rendering most core functionalities non-operational and severely impacting the user experience.",\n    "time_behaviour": {\n        "rating": "Fair",\n        "findings": [\n            "Average response times are generally good for most endpoints, with GET /api/product/{id} at 43.92ms and DELETE /api/product/{id} at 43.08ms. Even the file operation GET /api/product/{productId}/image has a reasonable average of 106.41ms.",\n            "However, P95 response times reveal significant inconsistency and slowness for certain operations, particularly for PUT /api/product/{id} which reached 910ms. Other high P95s include GET /api/product/{productId}/image at 530ms and POST /api/product at 420ms, indicating potential bottlenecks or long-running failures."\n        ],\n        "recommendations": [\n            "Investigate the root causes of high P95 response times, especially for PUT, POST, and image retrieval operations, as these suggest potential inefficiencies even in the failure path.",\n            "Optimize database queries, business logic, or consider caching mechanisms to reduce latency and improve consistency for all operations once the underlying failure issues are resolved."\n        ]\n    },\n    "resource_utilisation": {\n        "rating": "Good",\n        "findings": [\n            "Resource utilization under a load of 10 users is notably low, with peak CPU at 25.62% and average CPU at 8.86%.",\n            "Memory usage is stable and low, peaking at 215.34 MB and averaging 212.62 MB.",\n            "It\'s crucial to understand that these low utilization figures are likely a direct consequence of the widespread request failures; the system is not successfully processing most requests and therefore is not adequately stressed."\n        ],\n        "recommendations": [\n            "After resolving the critical failure rates, re-evaluate resource utilization under a successful, sustained load to accurately gauge the system\'s true performance and capacity capabilities."\n        ]\n    },\n    "capacity": {\n        "rating": "Poor",\n        "findings": [\n            "The system demonstrates severe capacity and reliability issues, evidenced by an alarming overall failure rate of 86.21% across 174 total requests.",\n            "A critical finding is that 6 out of 7 endpoints (GET /api/product/{id}, POST /api/product, GET /api/product/{productId}/image, PUT /api/product/{id}, DELETE /api/product/{id}, GET /api/products/search) exhibit a 100.0% failure rate, indicating a fundamental breakdown in functionality for nearly all key operations.",\n            "Only GET /api/products successfully processes requests with a 0.0% failure rate."\n        ],\n        "recommendations": [\n            "Initiate an immediate and thorough investigation into the root causes of the 100% failure rates across almost all endpoints. This must be the top priority.",\n            "Focus debugging efforts on server-side error logs, database connectivity, API contract validation (request payload/parameters), and authentication/authorization mechanisms.",\n            "Implement robust error handling and more informative error responses to expedite future debugging and issue resolution."\n        ]\n    },\n    "endpoint_findings": [\n        {\n            "endpoint": "GET /api/product/{id}",\n            "score": 71.8,\n            "issue": "Complete failure (100.0% failure rate) to retrieve individual product details.",\n            "recommendation": "Examine server-side logic for ID parsing, database queries for single-item retrieval, and ensure correct data is being returned, if any."\n        },\n        {\n            "endpoint": "POST /api/product",\n            "score": 69.5,\n            "issue": "Complete failure (100.0% failure rate) to create new products.",\n            "recommendation": "Debug the product creation workflow, including request body validation, database insertion logic, and any associated business rules or transaction management."\n        },\n        {\n            "endpoint": "GET /api/product/{productId}/image",\n            "score": 75.0,\n            "issue": "Complete failure (100.0% failure rate) to retrieve product images.",\n            "recommendation": "Verify file storage access permissions, image path resolution, and the logic responsible for serving image content. Ensure the `productId` used for image retrieval corresponds to valid and accessible product data."\n        },\n        {\n            "endpoint": "PUT /api/product/{id}",\n            "score": 61.6,\n            "issue": "Complete failure (100.0% failure rate) to update existing products, coupled with a critically high P95 response time of 910ms.",\n            "recommendation": "Prioritize debugging of the update operation\'s server-side logic, data validation, and database transaction integrity. Investigate why requests are taking so long to fail, suggesting potential deadlocks, timeouts, or unhandled exceptions."\n        },\n        {\n            "endpoint": "DELETE /api/product/{id}",\n            "score": 71.5,\n            "issue": "Complete failure (100.0% failure rate) to delete products.",\n            "recommendation": "Review the deletion logic, including any foreign key constraints, cascading deletes, and ensure the authenticated user has appropriate permissions to perform deletions."\n        },\n        {\n            "endpoint": "GET /api/products/search",\n            "score": 75.0,\n            "issue": "Complete failure (100.0% failure rate) for the product search functionality.",\n            "recommendation": "Debug the search query parsing, indexing mechanisms (if applicable), and database search logic. Ensure search parameters are correctly handled and filtered, and that the search engine is operational."\n        }\n    ],\n    "priority_issues": [\n        "The overwhelming 100% failure rate across critical write, read, update, and delete operations (e.g., POST /api/product, PUT /api/product/{id}, GET /api/product/{id}, DELETE /api/product/{id}), rendering the core API virtually unusable.",\n        "The PUT /api/product/{id} endpoint has the lowest score (61.6) and a critically high P95 response time (910ms) despite its 100% failure rate, indicating severe performance and functional issues."\n    ]\n}\n', 'errors': []}
        if not eval_result['success']:
            return jsonify({'error': 'Evaluation failed', 'details': eval_result['errors']}), 400
        
        # Save result to database
        eval_id = insert(file.filename, detection['build_system'], result['metrics'], eval_result['evaluation'], eval_result['evaluation'].get('overall_rating'), result['errors'])
        
        print()
        print({'detected endpoints': static_endpoints, 'detected_port': port, 'metrics': result['metrics'], 'scores': scores, 'evaluation': eval_result['evaluation'], 'run_errors': result['errors']})
        return jsonify({'eval_id': eval_id, 'detected endpoints': static_endpoints, 'detected_port': port, 'metrics': result['metrics'], 'scores': scores, 'evaluation': eval_result['evaluation'], 'run_errors': result['errors']})

    finally:
        shutil.rmtree(extract_path) # Clean up extracted files

@app.route('/history')
def history():
    evaluations = get_all()
    return jsonify({'evaluations': evaluations})



if __name__ == '__main__':
    app.run(debug=True)
