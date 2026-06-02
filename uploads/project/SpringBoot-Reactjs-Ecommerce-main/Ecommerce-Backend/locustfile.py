from locust import HttpUser,task, between
class AppUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def endpoint_0(self):
        with self.client.get('/api/products', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_1(self):
        with self.client.get('/api/product/1', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_2(self):
        with self.client.post('/api/product', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_3(self):
        with self.client.get('/api/product/1/image', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_4(self):
        with self.client.put('/api/product/1', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_5(self):
        with self.client.delete('/api/product/1', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
    @task
    def endpoint_6(self):
        with self.client.get('/api/products/search', catch_response=True) as response:
            if reponse.status_code == 0:
                response.failure('No response')
            elif response.status_code >= 400:
                response.failure(f'Status code {response.status_code}')
            else:
                response.success()
        
