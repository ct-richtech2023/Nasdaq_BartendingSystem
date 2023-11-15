from loguru import logger


def sink(message):
    ip = message.record["extra"]["ip"]
    with open(f'{ip}.log', 'a') as file:
        file.write(message)


logger.add(sink)
logger.add('ip.log')


class Worker:
    def __init__(self, ip):
        self.ip = ip
        self.log(ip)

    def log(self, msg):
        logger.bind(ip=self.ip).info(f'ping {msg}')


Worker('192.168.2.1')
Worker('192.168.2.2')
Worker('192.168.2.3')
