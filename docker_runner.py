import docker, os, re, subprocess
from locust_runner import run_test, get_endpoints, wait_for_app

client = docker.from_env()

def detect_java_version(project_root): 
    """Detect Java version to use appropriate base image for Dockerfile"""
    pom_path = os.path.join(project_root, 'pom.xml')
    if not os.path.exists(pom_path): 
        return '17' # default to 17 if no pom.xml found

    with open(pom_path, 'r', errors='ignore') as file:
        content = file.read()

    # Look for java.version in pom.xml (common convention) 
    match = re.search(r'<java\.version>(\d+)</java\.version>', content)
    if match:
        return match.group(1)

    # Look for maven.compiler.source as fallback
    match = re.search(r'<maven\.compiler\.source>(\d+)</maven\.compiler\.source>', content)
    if match:
        return match.group(1)
    
    return '17' # default if no version found

def needs_database(project_root):
    """Check if project requires an external database"""
    pom_path = os.path.join(project_root, 'pom.xml')
    if not os.path.exists(pom_path):
        return False, None
    
    with open(pom_path, 'r', errors='ignore') as file:
        content = file.read().lower()

    if 'mysql' in content:
        return True, 'mysql'
    elif 'postgresql' in content or 'postgres' in content:
        return True, 'postgresql'
    elif 'h2' in content:
        return False, 'h2' # h2 runs in memotry so no external database is needed
    
    return False, None

def dockerfile(build_system, project_root):
    """Generate Dockerfile content based on build system and java version"""
    java_version = detect_java_version(project_root)
    if build_system == 'maven':
        return f"""\
FROM maven:3.9-eclipse-temurin-{java_version}
WORKDIR /app
COPY . .
RUN mvn package -DskipTests -q
CMD ["sh", "-c", "java -jar target/*.jar"]
"""
    
    elif build_system == 'gradle':
        return f"""\
FROM gradle:8.5-jdk{java_version}
WORKDIR /app
COPY . .
RUN gradle build -x test -q
CMD ["sh", "-c", "java -jar build/libs/*.jar"]
"""
    else:
        raise ValueError(f'Unsupported build system: {build_system}')
    

def write_dockerfile(build_system, project_root):
    content = dockerfile(build_system, project_root)
    docker_path = os.path.join(project_root, 'Dockerfile')
    with open(docker_path, 'w') as f:
        f.write(content)

    print('Dockerfile written')
    return docker_path


def write_docker_compose(project_root, db_type, port):
    """Write docker-compose.yml file for projects needing databse"""
    if db_type == 'mysql':
        db_service = """
db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: appdb
      MYSQL_USER: user
      MYSQL_PASSWORD: password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10

"""
        db_env = """
      SPRING_DATASOURCE_URL: jdbc:mysql://db:3306/appdb
      SPRING_DATASOURCE_USERNAME: user
      SPRING_DATASOURCE_PASSWORD: password
      SPRING_DATASOURCE_DRIVER_CLASS_NAME: com.mysql.cj.jdbc.Driver
      SPRING_JPA_HIBERNATE_DDL_AUTO: create-drop
      SPRING_JPA_DATABASE_PLATFORM: org.hibernate.dialect.MySQL8Dialect
      
"""

    elif db_type == 'postgresql':
        db_service = """
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 5s
      retries: 10

"""
        db_env = """
      SPRING_DATASOURCE_URL: jdbc:postgresql://db:5432/appdb
      SPRING_DATASOURCE_USERNAME: user
      SPRING_DATASOURCE_PASSWORD: password
      SPRING_JPA_HIBERNATE_DDL_AUTO: create-drop
      SPRING_JPA_DATABASE_PLATFORM: org.hibernate.dialect.PostgreSQLDialect
      
"""
    compose_content = f"""\
version: '3.8'

services:
{db_service}
  app:
    build: .
    ports:
      - "{port}:{port}"
    environment:{db_env}
    depends_on:
      db:
        condition: service_healthy
"""
    with open(os.path.join(project_root, 'docker-compose.yml'), 'w') as f:
        f.write(compose_content)

    print('docker-compose.yml written')


def run_with_compose(project_root):
    """Run application using Docker Compose"""
    result = {
        'build_success': False,
        'run_success': False,
        'container': None,
        'errors': []
    }

    compose_file = os.path.join(project_root, 'docker-compose.yml')

    try:
        # Build with compose
        print('Building with Docker Compose...')
        build_proc = subprocess.run(
            ['docker-compose', '-f', compose_file, 'build'],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        if build_proc.returncode != 0:
            result['errors'].append(f'Compose build failed: {build_proc.stderr}')
            return result
        
        result['build_success'] = True
        print('Build successful')

        # Start services
        print('Starting services...')
        up_proc = subprocess.run(
            ['docker-compose', '-f', compose_file, 'up', '-d'],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        if up_proc.returncode != 0:
            result['errors'].append(f'Compose up failed: {up_proc.stderr}')
            return result
        
        print('Services started')
        result['container'] = 'compose'

    except Exception as e:
        result['errors'].append(f'Compose error: {str(e)}')

def stop_compose(project_root):
    """Stop and remove all compose services"""
    compose_file = os.path.join(project_root, 'docker-compose.yml')
    try: 
        subprocess.run(
            ['docker-compose', '-f', compose_file, 'down', '-v'],
            capture_output=True,
            cwd=project_root
        )
        print('Compose services stopped and remoces')

    except Exception as e:
        print(f'Error stopping compose: {e}')


def run_and_measure(project_root, build_system, endpoints, port=8080, timeout=60): # static endpoints
    """Run application and obtain metrics using Locust"""
    result = {
        'build_success': False,
        'run_success': False,
        'metrics': {},
        'errors': []
    }
    
    write_dockerfile(build_system, project_root)

    # check if Docker Compose needed  
    requires_db, db_type = needs_database(project_root)
    if requires_db: 
        print(f'Requires database: {requires_db} ({db_type})')
        write_docker_compose(project_root, db_type, port)
        compose_result = run_with_compose(project_root)

        if not compose_result['build_success']:
            result['errors'].extened(compose_result['errors'])
            return result
    
        result['build_success'] = True

        try:
            app_ready = wait_for_app('localhost', port, timeout=timeout)
            if not app_ready:
                result['errors'].append('App did not start within timeout')
                return result
            
            actual_endpoints = get_endpoints(project_root, 'localhost', port)

            if not actual_endpoints:
                result['errors'].append('No endpoints found for testing')
                result['run_success'] = False
                return result
        

            load_result = run_test(
            endpoints = actual_endpoints,
            container=None, # no single container object with docker compose
            host='localhost',
            port=port,
            duration=30,
            users=10,
            output_path=project_root    
            )

            result['metrics'] = load_result['metrics']
            result['errors'].extend(load_result['errors'])
            result['run_success'] = load_result['success']
        
        finally:
            stop_compose(project_root)

    else:
        container = None
        image_tag = 'eval_project:latest'
        try:
            # Build image
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
            print('Running container...')
            container = client.containers.run(
                image_tag, 
                detach=True, 
                mem_limit='512m', # resource limits
                nano_cpus=1_000_000_000, # equivalent to 1 CPU
                network_disabled=False, # enable network for load testing
                ports={f'{port}/tcp': port}, # expose app port for testing (port mapping allows us to access the app running inside the container from our host machine for load testing)
                remove=False) # returns container object
        
            print('Container started...')
            actual_endpoints = get_endpoints(project_root, 'localhost', port)
            if not actual_endpoints:
                result['errors'].append('No endpoints found for testing')
                result['run_success'] = False
                return result
        
            

            # Run load test and collect metrics from locust and docker
            load_result = run_test(
                endpoints = actual_endpoints,
                container=container,
                host='localhost',
                port=port,
                duration=30,
                users=10,
                output_path=project_root    
            )

            result['metrics'] = load_result['metrics']
            result['errors'].extend(load_result['errors'])
            result['run_success'] = load_result['success']


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


# print(detect_java_version('uploads/project/SpringBoot-Reactjs-Ecommerce-main/Ecommerce-Backend'))
# result = run_and_measure('uploads/SpringBoot-Reactjs-Ecommerce-main/Ecommerce-Backend', 'maven', [{'method': 'GET', 'path': '/api/products'}, {'method': 'GET', 'path': '/api/product/{id}'}, {'method': 'POST', 'path': '/api/product'}, {'method': 'GET', 'path': '/api/product/{productId}/image'}, {'method': 'PUT', 'path': '/api/product/{id}'}, {'method': 'DELETE', 'path': '/api/product/{id}'}, {'method': 'GET', 'path': '/api/products/search'}])
# print(result)
