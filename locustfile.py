import docker, time
from locust import Httpuser, task, between
client = docker.from_env()
