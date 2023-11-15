import threading
import time

from loguru import logger
from order import GetOrderThread
from requests import ConnectionError

from common import conf
from common.api import AudioInterface, CoffeeInterface
from common.db.crud import center as center_crud
from common.db.database import get_db
from common.define import TaskStatus, AudioConstant


def get_center_obj():
    """
    保证Center只初始化一次
    """
    if not Center.Instance:
        Center.Instance = Center()
    return Center.Instance


class TaskThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.run_flag = True
        self.wait_connect = 1800  #
        self.db_session = next(get_db())

    def run(self) -> None:
        while self.run_flag:
            task_record = center_crud.get_next_task(self.db_session)
            if task_record:
                sended = False
                wait_time = 0
                while not sended:
                    try:
                        result = CoffeeInterface.make(task_record.formula,task_record.type, task_record.cup, task_record.sweetness, task_record.ice, task_record.milk,
                                                      task_record.task_uuid, task_record.receipt_number, task_record.create_time)
                        if result:
                            task_record.status = TaskStatus.waiting
                            self.db_session.commit()
                        sended = True
                    except ConnectionError:
                        sended = False
                        time.sleep(2)
                        wait_time += 2
                        # if wait_time >= self.wait_connect:
                        #    self.run_flag = False
                        #    logger.error('has wait for milktea for 30min, please check and restart')
                        #    AudioInterface.gtts(AudioConstant.get_mp3_file(AudioConstant.TextCode.time_out))
                    except Exception as e:
                        logger.error('something error when send task to milktea. error={}'.format(str(e)))
                        break
            else:
                time.sleep(1)


class Center:
    Instance = None

    def __init__(self):
        # try:
        #     adam_config = conf.get_machine_config().get('adam')
        #     self.get_order_thread = GetOrderThread(adam_config.get('sn'))
        # except Exception as e:
        #     logger.error('init get order thread error, msg={}'.format(str(e)))
        #     exit(-1)
        # self.get_order_thread.setDaemon(True)
        # self.get_order_thread.start()

        self.task_thread = TaskThread()
        self.task_thread.setDaemon(True)
        self.task_thread.start()
