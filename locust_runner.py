import docker, time, os, requests, json, subprocess, threading, re
from  endpoint_detector import detect_endpoints, detect_port, discover_endpoints_from_actuator
from scorer import score_all_endpoints, categorise_endpoint, ENDPOINT_CATEGORIES
client = docker.from_env()


def sanitise_path(path):
    return re.sub(r'\{[^}]+\}', '1', path) # replace path variables like {id} with dummy value '1' for testing purposes

def generate_locust(endpoints, output_path):
    tasks = ''
    for i, ep in enumerate(endpoints):
        path = sanitise_path(ep['path'])
        tasks += f"""\
    @task
    def endpoint_{i}(self):
        with self.client.{ep['method'].lower()}('{path}', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {{response.status_code}}')
            else:
                response.success()
        
"""
    
    content = f"""\
from locust import HttpUser,task, between
class AppUser(HttpUser):
    wait_time = between(1, 2)

{tasks}"""
    locust_path = os.path.join(output_path, 'locustfile.py')
    with open(locust_path, 'w') as file:
        file.write(content)

    return locust_path

def wait_for_app(host, port, timeout=120):
    # Check if app is responding before starting tests
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f'http://{host}:{port}', timeout=2)
            if response.status_code < 500:
                print('App is responding')
                return True
            
        except Exception:
            time.sleep(2)
        
    return False


def get_endpoints(project_root, container, host, port):
    """
    Try dynamic discovery first, fall back to static analysis
    """
    # Always do static analysis as baseline
    static_endpoints = detect_endpoints(project_root)
    print(f'Static analysis found {len(static_endpoints)} endpoints')

    # Try Actuator for more accurate results
    actuator_endpoints = discover_endpoints_from_actuator(host, port)
    
    if actuator_endpoints:
        print(f'Actuator discovery found {len(actuator_endpoints)} endpoints')
        return actuator_endpoints
    
    if static_endpoints:
        print('Using static analysis endpoints')
        return static_endpoints

    return []

def run_test(endpoints, container, host, port, duration = 30, users = 10, output_path = '.'):
    result = {
        'success': False,
        'errors': [],
        'metrics': {}
       }
    
    # generate locustfile
    locust_path = generate_locust(endpoints, output_path)

    # wait for app to start
    print(f'Waiting for app on port {port}...')
    if not wait_for_app(host, port):
        result['errors'].append('App did not start within 120 seconds')
        return result

    print('App is ready, starting load test...')

    # run locust headlessly using commands
    locust_cmd = [
    'locust',
    '--headless',
    '--locustfile', locust_path,
    '--host', f'http://127.0.0.1:{port}',
    '--users', str(users),
    '--spawn-rate', '2',
    '--run-time', f'{duration}s',
    '--json',
    '--only-summary'
    ]

    # collect docker stats during the load test
    docker_stats = []
    def collect_docker_stats():
        for _ in range(duration):
            try:
                stats = container.stats(stream=False)
                cpu_stats = stats.get('cpu_stats', {})
                precpu_stats = stats.get('precpu_stats', {})

                cpu_delta = (
                    cpu_stats.get('cpu_usage', {}).get('total_usage', 0) -
                    precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                )
                system_delta = (
                    cpu_stats.get('system_cpu_usage', 0) -
                    precpu_stats.get('system_cpu_usage', 0)
                )
                cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0

                memory_stats = stats.get('memory_stats', {})
                memory_usage = memory_stats.get('usage', 0)

                docker_stats.append({
                    'cpu_percent': round(cpu_percent, 2),
                    'memory_mb': round(memory_usage / (1024 * 1024), 2)
                })
            except Exception:
                pass
            time.sleep(1)


    stats_thread = threading.Thread(target=collect_docker_stats)
    stats_thread.daemon = True # thread gets killed automatically when main thread exits or crashes
    stats_thread.start()

    try:
        proc = subprocess.run(
            locust_cmd,
            capture_output=True,
            text=True,
            timeout=duration + 30
        )

        stats_thread.join(timeout=5)
        print('Locust stdout:', proc.stdout)
        print('Locust stderr:', proc.stderr)

        # parse locust JSON output
        if proc.stdout:
            try:
                per_endpoint_metrics, aggregate = parse_locust_stats(
                    proc.stdout,
                    endpoints
                )

                scores = score_all_endpoints(per_endpoint_metrics)

                # Aggregate resource metrics from Docker stats
                cpu_samples = [s['cpu_percent'] for s in docker_stats]
                memory_samples = [s['memory_mb'] for s in docker_stats]

                result['metrics'] = {
                    'per_endpoint': per_endpoint_metrics,
                    'aggregate': {
                        'total_requests': aggregate.get('num_requests', 0),
                        'failed_requests': aggregate.get('num_failures', 0),
                        'failure_rate_percent': round(
                            aggregate.get('num_failures', 0) /
                            aggregate.get('num_requests', 1) * 100, 2
                        ),
                        'requests_per_second': round(
                            aggregate.get('requests_per_sec', 0) or
                            aggregate.get('current_rps', 0), 2
                        ),
                        'cpu_peak_percent': round(max(cpu_samples), 2) if cpu_samples else 0,
                        'cpu_average_percent': round(
                            sum(cpu_samples) / len(cpu_samples), 2
                        ) if cpu_samples else 0,
                        'memory_peak_mb': round(max(memory_samples), 2) if memory_samples else 0,
                        'memory_average_mb': round(
                            sum(memory_samples) / len(memory_samples), 2
                        ) if memory_samples else 0,
                        'concurrent_users': users
                    },
                    'scores': scores
                }

                result['run_success'] = True

            except Exception as e:
                result['errors'].append(f'Stats parsing failed: {str(e)}')
        else:
            result['errors'].append('Locust produced no output')
            if proc.stderr:
                result['errors'].append(proc.stderr[:500])

    except subprocess.TimeoutExpired:
        result['errors'].append('Load test timed out')
    except Exception as e:
        result['errors'].append(f'Load test failed: {str(e)}')

    return result


def parse_locust_stats(locust_output, endpoints):
    """Parse Locust JSON output into per-endpoint metrics"""
    try:
        stats_list = json.loads(locust_output)
    except json.JSONDecodeError:
        return {}, {}

    # Build a map of path -> stats
    endpoint_stats = {}
    aggregate = {}

    for stat in stats_list:
        name = stat.get('name', '')
        if name == 'Aggregated':
            aggregate = stat
        else:
            endpoint_stats[name] = stat

    # Match stats back to our endpoints
    per_endpoint_metrics = {}
    for ep in endpoints:
        path = sanitise_path(ep['path'])
        method = ep['method'].upper()
        category = categorise_endpoint(method, ep['path'])

        # Locust names entries as "GET /api/products"
        locust_key = f"{method} {path}"
        stat = endpoint_stats.get(locust_key, {})

        per_endpoint_metrics[locust_key] = {
            'method': method,
            'path': ep['path'],
            'sanitised_path': path,
            'category': category,
            'category_description': ENDPOINT_CATEGORIES.get(
                category, {}
            ).get('description', ''),
            'metrics': {
                'avg_response_time_ms': round(
                    stat.get('avg_response_time', 0), 2
                ),
                'min_response_time_ms': round(
                    stat.get('min_response_time', 0), 2
                ),
                'max_response_time_ms': round(
                    stat.get('max_response_time', 0), 2
                ),
                'p95_response_time_ms': round(
                    stat.get('response_time_percentile_0.95', 0) or
                    stat.get('response_time_percentile_95', 0), 2
                ),
                'requests_per_second': round(
                    stat.get('requests_per_sec', 0) or
                    stat.get('current_rps', 0), 2
                ),
                'total_requests': stat.get('num_requests', 0),
                'failed_requests': stat.get('num_failures', 0),
                'failure_rate_percent': round(
                    stat.get('num_failures', 0) /
                    stat.get('num_requests', 1) * 100, 2
                ) if stat.get('num_requests', 0) > 0 else 0
            }
        }

    return per_endpoint_metrics, aggregate

# locust_path = generate_locust([{'method': 'GET', 'path': '/api/products'}, {'method': 'GET', 'path': '/api/product/{id}'}, {'method': 'POST', 'path': '/api/product'}, {'method': 'GET', 'path': '/api/product/{productId}/image'}, {'method': 'PUT', 'path': '/api/product/{id}'}, {'method': 'DELETE', 'path': '/api/product/{id}'}, {'method': 'GET', 'path': '/api/products/search'}], 'uploads/project/SpringBoot-Reactjs-Ecommerce-main/Ecommerce-Backend')