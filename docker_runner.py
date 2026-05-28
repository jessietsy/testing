import docker, os, time
from locust_runner import run_test

client = docker.from_env()

DOCKERFILE_MAVEN = """\
FROM maven:3.9-eclipse-temurin-17
WORKDIR /app
COPY . .
RUN mvn package -DskipTests -q
CMD ["sh", "-c", "java -jar target/*.jar"]
"""

DOCKERFILE_GRADLE = """\
FROM gradle:8.5-jdk17
WORKDIR /app
COPY . .
RUN gradle build -x test -q
CMD ["sh", "-c", "java -jar build/libs/*.jar"]
"""

def dockerfile(build_system):
    if build_system == 'maven':
        return DOCKERFILE_MAVEN
    elif build_system == 'gradle':
        return DOCKERFILE_GRADLE
    else:
        raise ValueError(f'Unsupported build system: {build_system}')
    

def write_dockerfile(build_system, extract_path):
    content = dockerfile(build_system)
    docker_path = os.path.join(extract_path, 'Dockerfile')
    with open(docker_path, 'w') as f:
        f.write(content)
    return docker_path

def run_and_measure(project_root, build_system, endpoints):
    result = {
        'build_success': False,
        'run_success': False,
        'metrics': {},
        'errors': []
    }

    container = None
    image_tag = 'eval_project:latest'
    try:
        # Build image
        write_dockerfile(build_system, project_root)
        print('Building Docker image...')
        image, logs = client.images.build(path=project_root, tag=image_tag, rm=True) # method returns tuple with image object and logs generator
        for log in logs:
            if 'stream' in log:
                print(log['stream'], end='') # print build output in real time
        result['build_success'] = True
        print('Build successful')
    
    except docker.errors.BuildError as e:
        result['errors'].append(f'Build error: {str(e)}')
        return result
    
    try: 
        # Run container with port exposed (for locust)
        # start_time = time.time()
        print('Running container...')
        container = client.containers.run(
            image_tag, 
            detach=True, 
            mem_limit='512m', # resource limits
            nano_cpus=1_000_000_000, # equivalent to 1 CPU
            network_disabled=True, 
            ports={'8080/tcp': 8080}, # expose app port for testing 
            remove=False) # returns container object
        
        print('Container started, waiting for it to finish...')

        # Run load test and collect metrics from locust and docker
        load_result = run_test(
            endpoints = endpoints,
            container=container,
            host='localhost',
            port=8080,
            duration=30,
            users=10,
            output_path=project_root    
        )

        result['metrics'] = load_result['metrics']
        result['errors'].extend(load_result['errors'])
        result['run_success'] = load_result['success']



        # # Wait for container to finish or timeout
        # try:
        #     container.wait(timeout=timeout) # avoid hanging indefinitely
        # except Exception:
        #     result['errors'].append(f'Container timed out after {timeout} seconds')
        


        # end_time = time.time()

        # Get Docker metrics
        # stats = container.stats(stream=False)

        # cpu_stats = stats.get('cpu_stats', {})
        # precpu_stats = stats.get('precpu_stats', {})

        # cpu_delta = (
        #     cpu_stats.get('cpu_usage', {}).get('total_usage', 0) -
        #     precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
        # )

        # system_cpu = cpu_stats.get('system_cpu_usage')
        # presystem_cpu = precpu_stats.get('system_cpu_usage')

        # system_delta = system_cpu - presystem_cpu if system_cpu and presystem_cpu else 0
        # cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0

        # memory_stats = stats.get('memory_stats', {})
        # memory_usage = memory_stats.get('usage', 0)
        # memory_limit = memory_stats.get('limit', 1)
        # memory_percent = (memory_usage / memory_limit) * 100

        # result['metrics'] = {
        #     'response_time_seconds': round(end_time - start_time, 2),
        #     'cpu_percent': round(cpu_percent, 2),
        #     'memory_usage_mb': round(memory_usage / (1024 * 1024), 2),
        #     'memory_percent': round(memory_percent, 2)
        # }
        # result['run_success'] = True



    except Exception as e:
        result['errors'].append(f'Run error: {str(e)}')
    
    finally:
        # Clean up regardless of success or failure
        if container:
            try:
                container.stop()
                container.remove()
            except Exception:
                pass
        if image: 
            try: 
                client.images.remove(image=image_tag, force=True)
            except Exception:
                pass
    return result

