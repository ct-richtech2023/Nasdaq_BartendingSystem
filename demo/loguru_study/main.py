import os.path

from loguru import logger


class A:
    def __init__(self, number):
        self.number = number
        self.count = number % 3

    def independent_log(self):
        logger.add('{}.log'.format(self.count))
        logger.info("number={} count={}".format(self.number, self.count))


if __name__ == '__main__':
    current = os.path.dirname(__file__)
    for i in range(3):
        path = os.path.join(current, '{}.log'.format(i))
        if os.path.exists(path):
            os.remove(path)

    for i in range(10):
        A(i).independent_log()
