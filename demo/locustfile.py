from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def hello_world(self):
        self.client.get("/drink/new_order?location=L0Y81R5W16NP9")
        # self.client.get("/world")