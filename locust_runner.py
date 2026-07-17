import docker, time, os, requests, json, subprocess, threading, re
from  endpoint_detector import detect_endpoints, detect_port, discover_endpoints_from_actuator
from scorer import score_all_endpoints, categorise_endpoint, ENDPOINT_CATEGORIES
client = docker.from_env()


def sanitise_path(path):
    return re.sub(r'\{[^}]+\}', '1', path) # replace path variables like {id} with dummy value '1' for testing purposes

def generate_locust(endpoints, output_path, seed_config=None):
    if seed_config:
        content = build_isolated_locustfile(endpoints, seed_config)
    else:
        content = build_basic_locustfile(endpoints)

    print(content)
    locust_path = os.path.join(output_path, 'locustfile.py')
    with open(locust_path, 'w') as file:
        file.write(content)

    return locust_path

def build_isolated_locustfile(endpoints, seed_config):
    create_path = seed_config['create_endpoint']
    create_body = seed_config['create_body']
    id_field = seed_config.get('id_field', 'id')

    # Build delete path using dynamic ID
    delete_ep = next(
        (ep for ep in endpoints if ep['method'].upper() == 'DELETE'),
        None
    )
    delete_path = sanitise_path(delete_ep['path']).replace('1', '{self.resource_id}') \
        if delete_ep else None

    on_stop_block = f"""
    def on_stop(self):
        if self.resource_id:
            self.client.delete(f"{delete_path}")
""" if delete_path else ""

    tasks = build_tasks(
        endpoints,
        skip_method='DELETE',
        use_dynamic_id=True
    )

    return f"""\
from locust import HttpUser, task, between
import json

class AppUser(HttpUser):
    wait_time = between(1, 2)
    resource_id = None

    def on_start(self):
        response = self.client.post(
            "{create_path}",
            json={create_body},
            catch_response=True
        )
        if response.status_code in [200, 201]:
            try:
                data = response.json()
                self.resource_id = data.get('{id_field}') or 1
                response.success()
            except Exception:
                self.resource_id = 1
                response.success()
        else:
            self.resource_id = 1
            response.failure(f"Seeding failed: {{response.status_code}}")
{on_stop_block}
{tasks}
"""

def build_basic_locustfile(endpoints):
    tasks = build_tasks(endpoints, use_dynamic_id=False)
    return f"""\
from locust import HttpUser, task, between

class AppUser(HttpUser):
    wait_time = between(1, 2)

{tasks}
"""
def build_tasks(endpoints, skip_method=None, use_dynamic_id=False):
    """Build Locust task functions generically for any endpoint list"""
    import re
    tasks = ""

    for i, ep in enumerate(endpoints):
        method = ep['method'].upper()

        if skip_method and method == skip_method:
            continue

        path = sanitise_path(ep['path'])
        category = categorise_endpoint(method, ep['path'])

        # Replace hardcoded 1 with dynamic resource_id if isolating
        if use_dynamic_id:
            path = re.sub(r'/1(/|$)', r'/{self.resource_id}\1', path)
            # Wrap in f-string if dynamic
            path_str = f'f"{path}"' if 'self.resource_id' in path else f'"{path}"'
        else:
            path_str = f'"{path}"'

        # Append search parameter for search endpoints
        if category == 'search':
            if use_dynamic_id:
                path_str = path_str.rstrip('"') + '?q=test"'
            else:
                path_str = f'"{path}?q=test"'

        if method in ['GET', 'DELETE']:
            tasks += f"""\
    @task
    def endpoint_{i}(self):
        with self.client.{method.lower()}({path_str}, catch_response=True) as response:
            if response.status_code >= 400:
                response.failure(f"Got {{response.status_code}}")
            else:
                response.success()

"""
        elif method in ['POST', 'PUT', 'PATCH']:
            tasks += f"""\
    @task
    def endpoint_{i}(self):
        with self.client.{method.lower()}(
            {path_str},
            json={{}},
            catch_response=True
        ) as response:
            if response.status_code >= 400:
                response.failure(f"Got {{response.status_code}}")
            else:
                response.success()

"""

    return tasks

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


def get_endpoints(project_root, host, port):
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
        print(f'Dynamically detected endpoints: {actuator_endpoints}')
        return actuator_endpoints
    
    if static_endpoints:
        print('Using static analysis endpoints')
        print(f'Statically detected endpoints: {static_endpoints}')
        return static_endpoints

    return []

def run_test(endpoints, container, host, port, duration = 30, users = 10, output_path = '.', seed_config=None):
    result = {
        'success': False,
        'errors': [],
        'metrics': {},
        'test_strategy': 'isolated' if seed_config else 'basic'
       }
    
    # generate locustfile
    locust_path = generate_locust(endpoints, output_path, seed_config)

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
                per_endpoint_metrics, aggregate_locust = parse_locust_stats(
                    proc.stdout,
                    endpoints
                )
                print(f'per_endpoint_metrics: {per_endpoint_metrics}')
                print()
                print(f'aggregate_locust: {aggregate_locust}')
                print()
                print(f'docker stats: {docker_stats}')
                print()
                # scores = score_all_endpoints(per_endpoint_metrics, docker_stats)

                # Aggregate resource metrics from Docker stats
                cpu_samples = [s['cpu_percent'] for s in docker_stats]
                memory_samples = [s['memory_mb'] for s in docker_stats]

                # Aggregate all metrics (Locust and Docker) into a single dictionary for scoring and evaluation
                # aggregate_all = {
                #         'total_requests': aggregate_locust.get('num_requests', 0),
                #         'failed_requests': aggregate_locust.get('num_failures', 0),
                #         'failure_rate_percent': round(
                #             aggregate_locust.get('num_failures', 0) /
                #             aggregate_locust.get('num_requests', 1) * 100, 2
                #         ),
                #         'requests_per_second': round(
                #             aggregate_locust.get('requests_per_sec', 0) or
                #             aggregate_locust.get('current_rps', 0), 2
                #         ),
                #         'cpu_peak_percent': round(max(cpu_samples), 2) if cpu_samples else 0,
                #         'cpu_average_percent': round(
                #             sum(cpu_samples) / len(cpu_samples), 2
                #         ) if cpu_samples else 0,
                #         'memory_peak_mb': round(max(memory_samples), 2) if memory_samples else 0,
                #         'memory_average_mb': round(
                #             sum(memory_samples) / len(memory_samples), 2
                #         ) if memory_samples else 0,
                #         'concurrent_users': users
                # }

                aggregate_all = get_aggregate(per_endpoint_metrics, docker_stats, users)
                scores = score_all_endpoints(per_endpoint_metrics, aggregate_all)
            

                result['metrics'] = {
                    'per_endpoint': per_endpoint_metrics,
                    'aggregate': aggregate_all,
                    # 'aggregate': {
                    #     'total_requests': aggregate.get('num_requests', 0),
                    #     'failed_requests': aggregate.get('num_failures', 0),
                    #     'failure_rate_percent': round(
                    #         aggregate.get('num_failures', 0) /
                    #         aggregate.get('num_requests', 1) * 100, 2
                    #     ),
                    #     'requests_per_second': round(
                    #         aggregate.get('requests_per_sec', 0) or
                    #         aggregate.get('current_rps', 0), 2
                    #     ),
                    #     'cpu_peak_percent': round(max(cpu_samples), 2) if cpu_samples else 0,
                    #     'cpu_average_percent': round(
                    #         sum(cpu_samples) / len(cpu_samples), 2
                    #     ) if cpu_samples else 0,
                    #     'memory_peak_mb': round(max(memory_samples), 2) if memory_samples else 0,
                    #     'memory_average_mb': round(
                    #         sum(memory_samples) / len(memory_samples), 2
                    #     ) if memory_samples else 0,
                    #     'concurrent_users': users
                    # },
                    'scores': scores
                }

                result['success'] = True

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
        method = stat.get('method', '').upper()
        name = stat.get('name', '')
        key = f"{method} {name}"
        if name == 'Aggregated':
            aggregate = stat
        else:
            endpoint_stats[key] = stat

    # Match stats back to our endpoints
    per_endpoint_metrics = {}
    for ep in endpoints:
        path = sanitise_path(ep['path'])
        method = ep['method'].upper()
        category = categorise_endpoint(method, ep['path'])

        # Locust names entries as "GET /api/products"
        locust_key = f"{method} {path}"
        stat = endpoint_stats.get(locust_key, {})

        if not stat:
            print(f'No Locust data found for {locust_key}')
            continue

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
                    (stat.get('total_response_time', 0)/stat.get('num_requests', 0)) if stat.get('num_requests', 0) > 0 else 0, 2
                ),
                'min_response_time_ms': round(
                    stat.get('min_response_time', 0), 2
                ),
                'max_response_time_ms': round(
                    stat.get('max_response_time', 0), 2
                ),
                'p95_response_time_ms': round(
                    calculate_p95(stat.get('response_times', {})), 2
                ),

                'requests_per_second': calculate_avg_rps(stat.get('num_reqs_per_sec', {})
                ),

                'total_requests': stat.get('num_requests', 0),
                'failed_requests': stat.get('num_failures', 0),
                'failure_rate_percent': round(
                    (stat.get('num_failures', 0) /
                    stat.get('num_requests', 0))*100 if stat.get('num_requests', 0) > 0 else 0, 2
                ) 
            }
        }

    return per_endpoint_metrics, aggregate

def calculate_p95(response_times): # response times dictionary from locust stats
    if not response_times:
        return 0
    
    all_times = []
    for time_str, count in response_times.items():
        all_times.extend([int(time_str)] * count)
    
    all_times.sort()
    if not all_times:
        return 0
    
    index = int(0.95 * len(all_times)) - 1
    return all_times[min(index, len(all_times) - 1)] 
                 
def calculate_avg_rps(num_rps):
    if not num_rps:
        return 0
    values = list(num_rps.values())
    return round(sum(values) / len(values), 2)

def get_aggregate(per_endpoint_metrics, docker_stats, users):
    total_requests = sum(
        ep['metrics']['total_requests']
        for ep in per_endpoint_metrics.values()
    )
    total_failures = sum(
        ep['metrics']['failed_requests']
        for ep in per_endpoint_metrics.values()
    )

    cpu_samples = [s['cpu_percent'] for s in docker_stats]
    memory_samples = [s['memory_mb'] for s in docker_stats]

    return {
        'total_requests': total_requests,
        'failed_requests': total_failures,
        'failure_rate_percent': round(
            total_failures / total_requests * 100, 2
        ) if total_requests > 0 else 0,
        'cpu_peak_percent': round(max(cpu_samples), 2) if cpu_samples else 0,
        'cpu_average_percent': round(
            sum(cpu_samples) / len(cpu_samples), 2
        ) if cpu_samples else 0,
        'memory_peak_mb': round(max(memory_samples), 2) if memory_samples else 0,
        'memory_average_mb': round(
            sum(memory_samples) / len(memory_samples), 2
        ) if memory_samples else 0,
        'concurrent_users': users
    }


# locust_path = generate_locust([{'method': 'GET', 'path': '/api/products'}, {'method': 'GET', 'path': '/api/product/{id}'}, {'method': 'POST', 'path': '/api/product'}, {'method': 'GET', 'path': '/api/product/{productId}/image'}, {'method': 'PUT', 'path': '/api/product/{id}'}, {'method': 'DELETE', 'path': '/api/product/{id}'}, {'method': 'GET', 'path': '/api/products/search'}], 'uploads/project/SpringBoot-Reactjs-Ecommerce-main/Ecommerce-Backend')

def calculate_p95(response_times_dict):
    """
    Calculate p95 from Locust's response_times dict
    Keys are rounded response times, values are counts
    """
    if not response_times_dict:
        return 0

    # Build sorted list of all response times
    all_times = []
    for time_str, count in response_times_dict.items():
        all_times.extend([int(time_str)] * count)

    all_times.sort()

    if not all_times:
        return 0

    p95_index = int(len(all_times) * 0.95)
    return all_times[min(p95_index, len(all_times) - 1)]

def calculate_avg_rps(num_reqs_per_sec):
    """Calculate average requests per second from Locust's per-second dict"""
    if not num_reqs_per_sec:
        return 0
    values = list(num_reqs_per_sec.values())
    return round(sum(values) / len(values), 2)


