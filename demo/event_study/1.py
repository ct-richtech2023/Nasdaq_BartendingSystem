import time
from hashlib import md5

import eventlet
# note: this urllib import doesn't work in Python2
from eventlet.green.urllib.request import urlopen

urls = [
    "http://www.google.com/intl/en_ALL/images/logo.gif",
    # "https://wiki.secondlife.com/w/images/secondlife.jpg",
    "https://docs.celeryq.dev/en/stable/_static/celery_512.png",
]


def fetch(url):
    return urlopen(url).read()


pool = eventlet.GreenPool()

for body in pool.imap(fetch, urls):
    print("got body", len(body))
    print(body)


feed_url="123"
print(time.monotonic())
print(time.monotonic())