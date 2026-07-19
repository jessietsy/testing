from google import genai 
import json

client = genai.Client() # client gets API key from environment variable 'GEMINI_API_KEY' (if not set, it must be passed as argument)
model_used = 'gemini-3.5-flash'

def format_code_samples(samples): # select java files to send so that AI can help identify the causes behind the poor performance etc.
    pass

def prompt(metrics, build_system, scores):
    """Build prompt for LLM"""
    endpoint_summary = ""
    for key, ep in metrics.get('per_endpoint', {}).items():
        s = scores['endpoint_scores'][key]['scoring']
        m = ep['metrics']

        endpoint_summary += f"""
{ep['method']} {ep['path']} ({ep['category_description']})
  Score: {s['score']}/100 (Grade: {s['grade']})
  Avg response time: {m['avg_response_time_ms']}ms
  P95 response time: {m['p95_response_time_ms']}ms
  Failure rate: {m['failure_rate_percent']}%
"""

    agg = metrics.get('aggregate', {})

    return f"""You are a software quality evaluator.

OVERALL SCORE: {scores['overall_score']}/100 (Grade: {scores['grade']})

PER-ENDPOINT BREAKDOWN:
{endpoint_summary}

RESOURCE UTILISATION (under load of {agg.get('concurrent_users')} users):
- Peak CPU: {agg.get('cpu_peak_percent')}%
- Average CPU: {agg.get('cpu_average_percent')}%
- Peak memory: {agg.get('memory_peak_mb')} MB
- Average memory: {agg.get('memory_average_mb')} MB

CAPACITY:
- Total requests: {agg.get('total_requests')}
- Failed requests: {agg.get('failed_requests')}
- Overall failure rate: {agg.get('failure_rate_percent')}%

Each endpoint has been scored against thresholds appropriate for 
its type — for example file operations are allowed higher response 
times than simple reads. Reference specific endpoint scores and 
response times in your findings.

Respond in this JSON format:
{{
    "overall_rating": "Poor/Fair/Good/Excellent",
    "summary": "2-3 sentences referencing overall score of {scores['overall_score']}",
    "time_behaviour": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding referencing specific endpoints and times"],
        "recommendations": ["specific recommendation"]
    }},
    "resource_utilisation": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding referencing CPU and memory numbers"],
        "recommendations": ["specific recommendation"]
    }},
    "capacity": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding referencing failure rates"],
        "recommendations": ["specific recommendation"]
    }},
    "endpoint_findings": [
        {{
            "endpoint": "METHOD /path",
            "score": 0,
            "issue": "specific issue",
            "recommendation": "specific fix"
        }}
    ],
    "priority_issues": ["issue referencing specific endpoint and score"]
}}"""

def evaluate(metrics, build_system, scores):
    """Obtain evaluation from LLM model, parse and validate results"""
    result = {
        'success': False,
        'evaluation': None,
        'raw_response': None,
        'errors': [],
    }

    try:
        response = client.models.generate_content(
            model = model_used,
            contents = {'text': prompt(metrics, build_system, scores)}
        )

        clean_response = response.text.strip()
        
        if clean_response.startswith('```'):
            clean_response = clean_response.split('\n',1)[1] # only splits at the first newline, so it preserves the rest of the formatting in the response
        if clean_response.endswith('```'):
            clean_response = clean_response.rsplit('```',1)[0]

        result['raw_response'] = clean_response
        result['evaluation'] = json.loads(clean_response) # parse JSON response into python dict for easier use in frontend
        result['success'] = True
    
    except json.JSONDecodeError:
        result['errors'].append('Model returned an unexpected format. Raw response: ' + clean_response)
    except Exception as e:
        result['errors'].append('Error during evaluation: ' + str(e))

    return result



# result = {'build_success': True, 'run_success': True, 'metrics': {'per_endpoint': {'GET /api/products': {'method': 'GET', 'path': '/api/products', 'sanitised_path': '/api/products', 'category': 'list_read', 'category_description': 'Retrieving a list or collection', 'metrics': {'avg_response_time_ms': 92.7, 'min_response_time_ms': 9.55, 'max_response_time_ms': 770.61, 'p95_response_time_ms': 300, 'requests_per_second': 1.33, 'total_requests': 24, 'failed_requests': 0, 'failure_rate_percent': 0.0}}, 'GET /api/product/1': {'method': 'GET', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'list_read', 'category_description': 'Retrieving a list or collection', 'metrics': {'avg_response_time_ms': 43.92, 'min_response_time_ms': 8.07, 'max_response_time_ms': 551.11, 'p95_response_time_ms': 330, 'requests_per_second': 1.56, 'total_requests': 28, 'failed_requests': 28, 'failure_rate_percent': 100.0}}, 'POST /api/product': {'method': 'POST', 'path': '/api/product', 'sanitised_path': '/api/product', 'category': 'create', 'category_description': 'Creating a new resource', 'metrics': {'avg_response_time_ms': 64.79, 'min_response_time_ms': 9.67, 'max_response_time_ms': 420.4, 'p95_response_time_ms': 420, 'requests_per_second': 1.15, 'total_requests': 15, 'failed_requests': 15, 'failure_rate_percent': 100.0}}, 'GET /api/product/1/image': {'method': 'GET', 'path': '/api/product/{productId}/image', 'sanitised_path': '/api/product/1/image', 'category': 'file_operation', 'category_description': 'File upload, download or image operation', 'metrics': {'avg_response_time_ms': 106.41, 'min_response_time_ms': 13.32, 'max_response_time_ms': 720.74, 'p95_response_time_ms': 530, 'requests_per_second': 1.53, 'total_requests': 29, 'failed_requests': 29, 'failure_rate_percent': 100.0}}, 'PUT /api/product/1': {'method': 'PUT', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'update', 'category_description': 'Updating an existing resource', 'metrics': {'avg_response_time_ms': 75.96, 'min_response_time_ms': 10.48, 'max_response_time_ms': 910.2, 'p95_response_time_ms': 910, 'requests_per_second': 1.46, 'total_requests': 19, 'failed_requests': 19, 'failure_rate_percent': 100.0}}, 'DELETE /api/product/1': {'method': 'DELETE', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'delete', 'category_description': 'Deleting a resource', 'metrics': {'avg_response_time_ms': 43.08, 'min_response_time_ms': 7.81, 'max_response_time_ms': 450.41, 'p95_response_time_ms': 170, 'requests_per_second': 1.55, 'total_requests': 34, 'failed_requests': 34, 'failure_rate_percent': 100.0}}, 'GET /api/products/search': {'method': 'GET', 'path': '/api/products/search', 'sanitised_path': '/api/products/search', 'category': 'search', 'category_description': 'Search or filter operation', 'metrics': {'avg_response_time_ms': 41.93, 'min_response_time_ms': 9.0, 'max_response_time_ms': 240.31, 'p95_response_time_ms': 150, 'requests_per_second': 1.32, 'total_requests': 25, 'failed_requests': 25, 'failure_rate_percent': 100.0}}}, 'aggregate': {'total_requests': 174, 'failed_requests': 150, 'failure_rate_percent': 86.21, 'cpu_peak_percent': 25.62, 'cpu_average_percent': 8.86, 'memory_peak_mb': 215.34, 'memory_average_mb': 212.62, 'concurrent_users': 10}, 'scores': {'overall_score': 82.9, 'grade': 'B', 'sub_characteristics': {'time_behaviour': {'score': 100.0, 'grade': 'A', 'note': 'Average of response time scores across all endpoints'}, 'resource_utilisation': {'score': 100.0, 'grade': 'A', 'note': 'CPU and memory usage under load'}, 'capacity': {'score': 14.3, 'grade': 'F', 'note': 'Average of failure rate scores across all endpoints'}}, 'endpoint_scores': {'GET /api/products': {'method': 'GET', 'path': '/api/products', 'sanitised_path': '/api/products', 'category': 'list_read', 'category_description': 'Retrieving a list or collection', 'metrics': {'avg_response_time_ms': 92.7, 'min_response_time_ms': 9.55, 'max_response_time_ms': 770.61, 'p95_response_time_ms': 300, 'requests_per_second': 1.33, 'total_requests': 24, 'failed_requests': 0, 'failure_rate_percent': 0.0}, 'scoring': {'score': 97.5, 'grade': 'A', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 93.8, 'failure_rate_percent': 100}}}, 'GET /api/product/1': {'method': 'GET', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'list_read', 'category_description': 'Retrieving a list or collection', 'metrics': {'avg_response_time_ms': 43.92, 'min_response_time_ms': 8.07, 'max_response_time_ms': 551.11, 'p95_response_time_ms': 330, 'requests_per_second': 1.56, 'total_requests': 28, 'failed_requests': 28, 'failure_rate_percent': 100.0}, 'scoring': {'score': 71.8, 'grade': 'C', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 91.9, 'failure_rate_percent': 0}}}, 'POST /api/product': {'method': 'POST', 'path': '/api/product', 'sanitised_path': '/api/product', 'category': 'create', 'category_description': 'Creating a new resource', 'metrics': {'avg_response_time_ms': 64.79, 'min_response_time_ms': 9.67, 'max_response_time_ms': 420.4, 'p95_response_time_ms': 420, 'requests_per_second': 1.15, 'total_requests': 15, 'failed_requests': 15, 'failure_rate_percent': 100.0}, 'scoring': {'score': 69.5, 'grade': 'C', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 86.2, 'failure_rate_percent': 0}}}, 'GET /api/product/1/image': {'method': 'GET', 'path': '/api/product/{productId}/image', 'sanitised_path': '/api/product/1/image', 'category': 'file_operation', 'category_description': 'File upload, download or image operation', 'metrics': {'avg_response_time_ms': 106.41, 'min_response_time_ms': 13.32, 'max_response_time_ms': 720.74, 'p95_response_time_ms': 530, 'requests_per_second': 1.53, 'total_requests': 29, 'failed_requests': 29, 'failure_rate_percent': 100.0}, 'scoring': {'score': 75.0, 'grade': 'B', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 100, 'failure_rate_percent': 0}}}, 'PUT /api/product/1': {'method': 'PUT', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'update', 'category_description': 'Updating an existing resource', 'metrics': {'avg_response_time_ms': 75.96, 'min_response_time_ms': 10.48, 'max_response_time_ms': 910.2, 'p95_response_time_ms': 910, 'requests_per_second': 1.46, 'total_requests': 19, 'failed_requests': 19, 'failure_rate_percent': 100.0}, 'scoring': {'score': 61.6, 'grade': 'C', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 66.4, 'failure_rate_percent': 0}}}, 'DELETE /api/product/1': {'method': 'DELETE', 'path': '/api/product/{id}', 'sanitised_path': '/api/product/1', 'category': 'delete', 'category_description': 'Deleting a resource', 'metrics': {'avg_response_time_ms': 43.08, 'min_response_time_ms': 7.81, 'max_response_time_ms': 450.41, 'p95_response_time_ms': 170, 'requests_per_second': 1.55, 'total_requests': 34, 'failed_requests': 34, 'failure_rate_percent': 100.0}, 'scoring': {'score': 71.5, 'grade': 'C', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 91.2, 'failure_rate_percent': 0}}}, 'GET /api/products/search': {'method': 'GET', 'path': '/api/products/search', 'sanitised_path': '/api/products/search', 'category': 'search', 'category_description': 'Search or filter operation', 'metrics': {'avg_response_time_ms': 41.93, 'min_response_time_ms': 9.0, 'max_response_time_ms': 240.31, 'p95_response_time_ms': 150, 'requests_per_second': 1.32, 'total_requests': 25, 'failed_requests': 25, 'failure_rate_percent': 100.0}, 'scoring': {'score': 75.0, 'grade': 'B', 'metric_scores': {'avg_response_time_ms': 100, 'p95_response_time_ms': 100, 'failure_rate_percent': 0}}}}}}, 'errors': []}
# print(result)
# print(evaluate(result['metrics'], 'maven', result['metrics'].get('scores', {})))