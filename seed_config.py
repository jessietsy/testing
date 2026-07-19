import os, json
from google import genai 


def collect_entity_source(project_root):
    """Collect source of Java entity classes"""
    entity_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in ['target', 'build', '.git', 'test']]
        for filename in files:
            if filename.endswith('.java'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', errors='ignore') as f:
                        content = f.read()
                        if '@Entity' in content:
                            entity_files.append(f"// {filename}\n{content}")

                except Exception:
                    pass

    return '\n\n'.join(entity_files[:3]) if entity_files else None  # Limit to first 3 entity classes for brevity


def suggest_seed_config(endpoints, project_root):
    """Ask LLM to suggest a seed config based on entity source code if write endpoints detected"""

    entity_source = collect_entity_source(project_root)
    if not entity_source:
        return None
    
    post_endpoints = [ep for ep in endpoints if ep['method'].upper() == 'POST']
    delete_endpoints = [ep for ep in endpoints if ep['method'].upper() == 'DELETE']

    if not post_endpoints:
        return None # No write endpoints detected, no need to suggest seed config
    
    prompt = f"""
You are helping to generate test data for a load testing tool.

Given these Java entity classes, {entity_source}

And these detected POST endpoints: {[ep['path'] for ep in post_endpoints]}
And these detected DELETE endpoints: {[ep['path'] for ep in delete_endpoints]}

Generate a JSON seed configuration for load testing. The create_body must only include fields that are likely required - do not include id, createdAt, updatedAt, or other auto-generated fields. Use realistic but simple test values.

Respond ONLY with valid JSON in this exact format, no other text.
{{
    "create_endpoint": "/api/...",
    "create_body": {{ ... }},
    "id_field": "id",
    "delete_endpoint": "/api/.../<id placeholder>"
}}"""
    
    try:
        client = genai.Client() # client gets API key from environment variable 'GEMINI_API_KEY' (if not set, it must be passed as argument)
        model_used = 'gemini-3.5-flash'

        response = client.models.generate_content(
            model = model_used,
            contents = {'text': prompt}
        )

        clean_response = response.text.strip()
        
        if clean_response.startswith('```'):
            clean_response = clean_response.split('\n',1)[1] # only splits at the first newline, so it preserves the rest of the formatting in the response
        if clean_response.endswith('```'):
            clean_response = clean_response.rsplit('```',1)[0]

        suggestion = json.loads(clean_response)
        return suggestion

    except Exception as e:
        print(f"Error generating seed config suggestion: {e}")
        return None

# print(suggest_seed_config([{'method': 'GET', 'path': '/api/products'}, {'method': 'GET', 'path': '/api/product/{id}'}, {'method': 'POST', 'path': '/api/product'}, {'method': 'GET', 'path': '/api/product/{productId}/image'}, {'method': 'PUT', 'path': '/api/product/{id}'}, {'method': 'DELETE', 'path': '/api/product/{id}'}, {'method': 'GET', 'path': '/api/products/search'}] , 'uploads/SpringBoot-Reactjs-Ecommerce-main copy 4/Ecommerce-Backend'))

# text = '''```json
# {
#     "create_endpoint": "/api/product",
#     "create_body": {
#         "name": "Sample Product X",
#         "description": "A high-quality sample product for testing purposes.",
#         "brand": "TechCorp",
#         "price": 199.99,
#         "category": "Electronics",
#         "releaseDate": "2023-10-26T10:00:00Z",
#         "productAvailable": true,
#         "stockQuantity": 50
#     },
#     "id_field": "id",
#     "delete_endpoint": "/api/product/<id placeholder>"
# }
# ```'''

# text.strip()
# print(text.startswith('```'))
# print(text.endswith('```'))
# if text.startswith('```'):
#     text = text.split('\n',1)[1] # only splits at the first newline, so it preserves the rest of the formatting in the response

# if text.endswith('```'):
#     text = text.rsplit('```',1)[0]


# print(text)

