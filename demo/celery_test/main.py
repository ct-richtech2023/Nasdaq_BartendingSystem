import celery
from fastapi import FastAPI
import tasks

app = FastAPI()


@app.get("/")
def read_root():
    result = tasks.add.delay(2, 2)
    return {"2+2": result.get()}
