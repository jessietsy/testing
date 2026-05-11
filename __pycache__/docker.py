import docker

client = docker.from_env()

DOCKERFILE_MAVEN = """
FROM maven:"""