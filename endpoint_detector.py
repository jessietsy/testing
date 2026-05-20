import os
import re

# Match method-level mapping annotations
METHOD_ANNOTATION_PATTERN = re.compile(
    r'@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE
)

# Match @RequestMapping at method or class level
REQUEST_MAPPING_PATTERN = re.compile(
    r'@RequestMapping\s*\([^)]*value\s*=\s*["\']([^"\']+)["\'][^)]*(?:method\s*=\s*RequestMethod\.(\w+))?[^)]*\)',
    re.IGNORECASE
)

# Match class-level @RequestMapping for base path
CLASS_BASE_PATH_PATTERN = re.compile(
    r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE
)

METHOD_MAP = {
    'Get': 'GET',
    'Post': 'POST',
    'Put': 'PUT',
    'Delete': 'DELETE',
    'Patch': 'PATCH'
}

SKIP_FOLDERS = ['target', 'build', '.git', 'test', 'tests']

def detect_endpoints(project_root):
    endpoints = []
    java_files = collect_java_files(project_root)

    for file_path in java_files:
        file_endpoints = extract_endpoints_from_file(file_path)
        endpoints.extend(file_endpoints)

    # Deduplicate
    seen = set()
    unique_endpoints = []
    for ep in endpoints:
        key = (ep['method'], ep['path'])
        if key not in seen:
            seen.add(key)
            unique_endpoints.append(ep)

    return unique_endpoints

def collect_java_files(project_root):
    java_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]
        for filename in files:
            if filename.endswith('.java'):
                java_files.append(os.path.join(root, filename))
    return java_files

def extract_endpoints_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    # Only process controller files
    if not is_controller(content):
        return []

    base_path = extract_base_path(content)
    endpoints = []

    # Find method-level annotations
    for match in METHOD_ANNOTATION_PATTERN.finditer(content):
        http_method = METHOD_MAP.get(match.group(1).capitalize(), 'GET')
        path = match.group(2)
        full_path = combine_paths(base_path, path)
        endpoints.append({
            'method': http_method,
            'path': full_path
        })

    # Find @RequestMapping at method level
    for match in REQUEST_MAPPING_PATTERN.finditer(content):
        path = match.group(1)
        http_method = match.group(2) if match.group(2) else 'GET'
        full_path = combine_paths(base_path, path)
        endpoints.append({
            'method': http_method.upper(),
            'path': full_path
        })

    return endpoints

def is_controller(content):
    """Only extract from Spring controller classes"""
    return any(annotation in content for annotation in [
        '@RestController',
        '@Controller',
        '@RequestMapping'
    ])

def extract_base_path(content):
    """Find class-level @RequestMapping path to use as prefix"""
    # Look for class-level mapping — appears before the class declaration
    class_match = re.search(
        r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']'
        r'[^)]*\)[^{]*class\s+\w+',
        content,
        re.DOTALL
    )
    if class_match:
        return class_match.group(1)
    return ''

def combine_paths(base, path):
    """Combine base path and method path cleanly"""
    base = base.rstrip('/')
    path = path if path.startswith('/') else '/' + path
    return base + path

def detect_port(project_root):
    """Try to find the configured port from application properties"""
    port = 8080  # Spring Boot default

    # Check application.properties
    props_path = os.path.join(
        project_root, 'src', 'main', 'resources', 'application.properties'
    )
    if os.path.exists(props_path):
        with open(props_path, 'r', errors='ignore') as f:
            for line in f:
                if line.startswith('server.port'):
                    try:
                        port = int(line.split('=')[1].strip())
                    except ValueError:
                        pass

    # Check application.yml
    yml_path = os.path.join(
        project_root, 'src', 'main', 'resources', 'application.yml'
    )
    if os.path.exists(yml_path):
        with open(yml_path, 'r', errors='ignore') as f:
            content = f.read()
            match = re.search(r'port:\s*(\d+)', content)
            if match:
                try:
                    port = int(match.group(1))
                except ValueError:
                    pass

    return port

import requests

def discover_endpoints_from_actuator(host, port, timeout=30):
    """
    Query Spring Boot Actuator for registered endpoints.
    Returns list of endpoints or None if Actuator is not available.
    """
    try:
        response = requests.get(
            f'http://{host}:{port}/actuator/mappings',
            timeout=timeout
        )

        if response.status_code != 200:
            return None

        data = response.json()
        endpoints = []

        # Navigate actuator response structure
        contexts = data.get('contexts', {})
        for context in contexts.values():
            mappings = context.get('mappings', {})
            dispatcher = mappings.get('dispatcherServlets', {})
            
            for servlet in dispatcher.values():
                for mapping in servlet:
                    details = mapping.get('details', {})
                    request_mapping = details.get('requestMappingInfo', {})
                    
                    # Get methods
                    methods = request_mapping.get('methodsCondition', {}).get('methods', ['GET'])
                    
                    # Get patterns
                    patterns = request_mapping.get('patternValues', [])
                    if not patterns:
                        patterns = request_mapping.get('patterns', [])

                    for pattern in patterns:
                        # Skip actuator and error endpoints
                        if any(skip in pattern for skip in ['/actuator', '/error']):
                            continue
                        for method in methods:
                            endpoints.append({
                                'method': method,
                                'path': pattern
                            })

        return endpoints if endpoints else None

    except Exception:
        return None
    

print(detect_endpoints('uploads/project\\E-commerce-project-springBoot-master'))