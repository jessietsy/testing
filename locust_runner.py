import docker, time, os, requests, json, subprocess, threading
client = docker.from_env()


def generate_locust(endpoints, output_path):
    tasks = ''
    for i, ep in enumerate(endpoints):
        tasks += f"""\
        @task
        def endpoint_{i}(self):
            self.client.{ep['method'].lower()}('{ep['path']}')

        """
    
    content = f"""\
    from locust import HttpUser,task, between
    class AppUser(HttpUser):
        wait_time = between(1, 2)

    {tasks}
    """
    locust_path = os.path.join(output_path, 'locustfile.py')
    with open(locust_path, 'w') as file:
        file.write(content)

    return locust_path

def wait_for_app(host, port, timeout=60):
    # Check if app is responding before starting tests
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f'http://{host}:{port}', timeout=2)
            if response.status_code == 200:
                print('App is responding')
                return True
            
        except Exception:
            time.sleep(2)
        
    return False

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
        result['errors'].append('App did not start within 60 seconds')
        return result

    print('App is ready, starting load test...')

    # run locust headlessly using commands
    locust_cmd = [
    'locust',
    '--headless',
    '--locustfile', locust_path,
    '--host', f'http://{host}:{port}',
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

        # parse locust JSON output
        if proc.stdout:
            try:
                locust_stats = json.loads(proc.stdout)

                # extract aggregate stats
                aggregate = next(
                    (s for s in locust_stats if s.get('name') == 'Aggregated'),
                    locust_stats[-1] if locust_stats else {}
                )

                # docker resource stats during load
                cpu_samples = [s['cpu_percent'] for s in docker_stats]
                memory_samples = [s['memory_mb'] for s in docker_stats]

                result['metrics'] = {
                    # time behaviour
                    'avg_response_time_ms': round(aggregate.get('avg_response_time', 0), 2),
                    'min_response_time_ms': round(aggregate.get('min_response_time', 0), 2),
                    'max_response_time_ms': round(aggregate.get('max_response_time', 0), 2),
                    'p95_response_time_ms': round(aggregate.get('response_time_percentile_0.95', 0), 2),
                    'requests_per_second': round(aggregate.get('current_rps', 0), 2),

                    # resource utilisation
                    'cpu_peak_percent': round(max(cpu_samples), 2) if cpu_samples else 0,
                    'cpu_average_percent': round(sum(cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0,
                    'memory_peak_mb': round(max(memory_samples), 2) if memory_samples else 0,
                    'memory_average_mb': round(sum(memory_samples) / len(memory_samples), 2) if memory_samples else 0,

                    # capacity
                    'total_requests': aggregate.get('num_requests', 0),
                    'failed_requests': aggregate.get('num_failures', 0),
                    'failure_rate_percent': round(
                        aggregate.get('num_failures', 0) /
                        aggregate.get('num_requests', 1) * 100, 2
                    ),
                    'concurrent_users': users
                }

                result['success'] = True

            except (json.JSONDecodeError, IndexError) as e:
                result['errors'].append(f'Could not parse locust output: {str(e)}')
                if proc.stderr:
                    result['errors'].append(proc.stderr[:500])
        else:
            result['errors'].append('Locust produced no output')
            if proc.stderr:
                result['errors'].append(proc.stderr[:500])

    except subprocess.TimeoutExpired:
        result['errors'].append('Load test timed out')
    except Exception as e:
        result['errors'].append(f'Load test failed: {str(e)}')

    return result