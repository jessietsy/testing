from google import genai 
import json

client = genai.Client(api_key="AIzaSyCzZRdBKp8ov3axNLwgU0JhmTsytLckPxg") # client gets API key from environment variable 'GEMINI_API_KEY' (if not set, it must be passed as argument)
model_used = 'gemini-2.5-flash'

def format_code_samples(samples): # select java files to send so that AI can help identify the causes behind the poor performance etc.
    pass

def prompt(build_system, metrics):
    return f"""
    You are a software quality evaluator. Evaluate the following Java project against the ISO/IEC 25010 Performance Efficiency criteria

    ISO/IEC 25010 Performance Efficiency has three sub-charateristics:
    1. Time Behaviour: capability of a product to perform its specified function under specified conditions so that the response time and throughput rates meet the requirements
    2. Rsource Utilisation: capability of a product to use no more than the specified amount of resources to perform its function under specified conditions
    3. Capacity: capability of a product to meet requirements for the maximum limits of a product parameter

    Measured metrics:
    - Response time: {metrics.get('response_time_seconds', 'N/A')} seconds
    - CPU usage: {metrics.get('cpu_percent', 'N/A')}%
    - Memory usage: {metrics.get('memory_usage', 'N/A')} MB
    - Memory Percentage: {metrics.get('memory_percent', 'N/A')}%
    - Build system: {build_system}

    Provide your evaluation in the following JSON format exactly, with no additional text outside the JSON:
    {{
    "overall_rating": "Poor/Fair/Good/Excellent",
    "summary": "2-3 sentence overall summary",
    "time_behaviour": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding 1", "finding 2"],
        "recommendations": ["recommendation 1", "recommendation 2"]
    }},
    "resource_utilisation": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding 1", "finding 2"],
        "recommendations": ["recommendation 1", "recommendation 2"]
    }},
    "capacity": {{
        "rating": "Poor/Fair/Good/Excellent",
        "findings": ["finding 1", "finding 2"],
        "recommendations": ["recommendation 1", "recommendation 2"]
    }},
    "priority_issues": ["most urgent issue 1", "most urgent issue 2"]
}}"""

def evaluate(metrics, build_system):
    result = {
        'success': False,
        'evaluation': None,
        'raw_response': None,
        'errors': []
    }

    try:
        response = client.models.generate_content(
            model = model_used,
            contents = {'text': prompt(build_system, metrics)}
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

