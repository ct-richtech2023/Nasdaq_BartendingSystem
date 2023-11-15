from celery import Celery

app = Celery("tasks", broker='redis://localhost:6379/0', backend='redis://localhost')


@app.task
def add(x, y):
    return x + y


from celery.signals import celeryd_init

@celeryd_init.connect
def configure_worker12(sender=None, conf=None, **kwargs):
    print('123123123')
    print(sender)
    print( conf)
    print(kwargs)