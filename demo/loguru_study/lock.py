import fcntl
import threading
import time
import datetime as dt
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')


def writetoTxt(txtFile):
    id = threading.currentThread().getName()
    with open(txtFile, 'a+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
        logging.info("{0} acquire lock".format(id))
        print("content={}".format(f.read()))
        f.write("{} write from {} \r\n".format(dt.datetime.now(), id))
        # time.sleep(3)
    # 在with块外，文件关闭，自动解锁
    logging.info("{0} exit".format(id))


for i in range(1):
    myThread = threading.Thread(target=writetoTxt, args=("test.txt",))
    myThread.start()
