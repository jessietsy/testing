from google import genai 
import json

client = genai.Client(api_key="AIzaSyCzZRdBKp8ov3axNLwgU0JhmTsytLckPxg") # client gets API key from environment variable 'GEMINI_API_KEY' (if not set, it must be passed as argument)
model_used = 'gemini-2.5-flash'

def format_code_samples(samples): # select java files to send so that AI can help identify the causes behind the poor performance etc.
    pass

def prompt(metrics, build_system, scores):
    endpoint_summary = ""
    for key, ep in metrics.get('per_endpoint', {}).items():
        s = ep['scoring']
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
- Requests per second: {agg.get('requests_per_second')}

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
    result = {
        'success': False,
        'evaluation': None,
        'raw_response': None,
        'errors': [],
    }

    try:
        response = client.models.generate_content(
            model = model_used,
            contents = {'text': prompt(build_system, metrics, scores)}
        )

        clean_reponse = response.text.strip()
        
        if clean_reponse.startswith('```'):
            clean_reponse = clean_reponse.split('\n',1)[1] # only splits at the first newline, so it preserves the rest of the formatting in the response
        if clean_reponse.endswith('```'):
            clean_reponse = clean_reponse.rsplit('```',1)[0]

        result['raw_response'] = clean_reponse
        result['evaluation'] = json.loads(clean_reponse) # parse JSON response into python dict for easier use in frontend
        result['success'] = True
    
    except json.JSONDecodeError:
        result['errors'].append('Model returned an unexpected format. Raw response: ' + clean_reponse)
    except Exception as e:
        result['errors'].append('Error during evaluation: ' + str(e))

    return result

