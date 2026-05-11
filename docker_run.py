import docker, os

client = docker.from_env()

DOCKERFILE_MAVEN = """
FROM maven:3.9-eclipse-temurin 17
WORKDIR /app
COPY . .
RUN mvn package -DskipTests -q
CMD ["sh", "-c", "java -jar target/*.jar"]
"""

DOCKERFILE_GRADLE = """
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

def docker_build(extract_path, build_system):
    result = {
        'build_success': False,
        'run_success': False,
        'errors': []
    }
    image = None
    container = None
    image_tag = 'eval_project'
    try:
        # Build image
        write_dockerfile(build_system, extract_path)
        print('Building Docker image...')
        image, logs = client.images.build(path=extract_path, tag=image_tag, rm=True)
        result['build_success'] = True
        print('Build successful')
    
    except docker.errors.BuildError as e:
        result['errors'].append(f'Build error: {str(e)}')
        return result
    
    try: 
        # Run container
        print('Running container...')
        container = client.containers.run(image_tag, detach=True, network_disabled=True, remove=False)

        # Wait for container to finish or timeout
        try:
            container.wait(timeout=30) # avoid hanging indefinitely
        except Exception:
            result['errors'].append('Container timed out after 30 seconds')



    except Exception as e:
        result['errors'].append(f'Run error: {str(e)}')
    
    # finally:
    #     # Clean up regardless of success or failure
    #     if container:
    #         try:
    #             container.stop()
    #             container.remove()
    #         except Exception:
    #             pass
    #     if image: 
    #         try: 
    #             client.images.remove(image=image_tag, force=True)
    #         except Exception:
    #             pass
    # return result
    print(result)
    return result

docker_build('uploads/project', 'maven')
