import sys

sys.path.append('..')

import requests
import urllib
from loguru import logger

from common import define
from common.schemas import adam as adam_schema
from common.myerror import AdamError
from requests.exceptions import ConnectionError


def module_base_url(module):
    host, port = define.ServiceHost.localhost, getattr(define.ServicePort, module).value
    return "http://{}:{}".format(host, port)


class CenterInterface:
    base_url = module_base_url('center')

    @classmethod
    def new_order(cls, order: dict, token: str = 'richtech'):
        header = {'x-token': token}
        url = "{}/center/order".format(cls.base_url)
        res = requests.post(url, json=order, headers=header)
        logger.info('url={} data={}, result={}'.format(url, order, res.content))

    @classmethod
    def inner_new_order(cls, order: dict, token: str = 'richtech'):
        header = {'token': token}
        url = "{}/center/inner_order".format(cls.base_url)
        res = requests.post(url, json=order, headers=header)
        logger.info('url={} data={}, result={}'.format(url, order, res.content))

    @classmethod
    def get_one_order(cls, order_number, token: str = 'richtech'):
        header = {'token': token}
        param = {'inner': 1}
        url = "{}/center/order/{}".format(cls.base_url, order_number)
        res = requests.get(url, params=param, headers=header)
        logger.info('url={} order_number={}, result={}'.format(url, order_number, res.content))
        return res.json()

    @classmethod
    def inner_update_order(cls, update_dict, token: str = 'richtech'):
        header = {'token': token}
        url = "{}/center/order/inner_update".format(cls.base_url)
        res = requests.post(url, json=update_dict, headers=header)
        logger.info('url={} data={}, result={}'.format(url, update_dict, res.content))
        return res.json()

    @classmethod
    def inner_paid_order(cls, order_number, receipt_number, token: str = 'richtech'):
        params = {'order_number': order_number, 'receipt_number': receipt_number}
        header = {'token': token}
        url = "{}/center/order/inner_paid".format(cls.base_url)
        res = requests.post(url, params=params, headers=header)
        logger.info('url={} order_number={}, result={}'.format(url, order_number, res.content))
        return res.json()

    @classmethod
    def update_task_status(cls, task_uuid, status, token: str = 'richtech'):
        params = {'task_uuid': task_uuid, 'status': status}
        header = {'token': token}
        url = "{}/center/order/task/status".format(cls.base_url)
        res = requests.post(url, params=params, headers=header)
        logger.info('url={} task_uuid={}, result={}'.format(url, task_uuid, res.content))
        return res.json()


class AudioInterface:
    base_url = module_base_url('audio')

    @classmethod
    def tts(cls, text, sync: bool = True):
        params = {'text': text, 'sync': sync}
        url = "{}/audio/tts".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def gtts(cls, text, sync: bool = False):
        params = {'text': text, 'sync': sync}
        url = "{}/audio/gtts".format(cls.base_url)
        try:
            res = requests.post(url, params=params, timeout=1)
            logger.info('url={} params={}, result={}'.format(url, params, res.content))
        except ConnectionError:
            pass

    @classmethod
    def weather(cls, lat=None, lon=None, units=None):
        params = {}
        if lat:
            params['lat'] = lat
        if lon:
            params['lon'] = lon
        if units:
            params['units'] = units
        url = "{}/audio/weather".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def music(cls, name, delay=None):
        params = {'name': name, 'delay': delay}
        url = "{}/audio/music".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def stop(cls):
        url = "{}/audio/stop".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={}, result={}'.format(url, res.content))

    @classmethod
    def sound(cls, name):
        params = {'name': name}
        url = "{}/audio/sound".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))


class CoffeeInterface:
    base_url = module_base_url('coffee')

    @classmethod
    def make(cls, formula, type, cup, sweetness, ice, milk, task_uuid=None, receipt_number='', create_time=None):
        params = {'formula': formula, 'type': type, 'cup': cup, 'sweetness': sweetness, 'task_uuid': task_uuid,
                  'ice': ice, 'milk': milk, 'receipt_number': receipt_number}
        if create_time:
            params['create_time'] = create_time
        if task_uuid:
            params['task_uuid'] = task_uuid
        url = "{}/coffee/make".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, code={}, result={}'.format(url, params, res.status_code, res.content))
        if res.status_code == 200:
            return True
        return False

    @classmethod
    def exist_next(cls):
        url = "{}/coffee/task/next".format(cls.base_url)
        res = requests.get(url)
        if res.status_code == 200:
            logger.info('check if exist_next, result={}'.format(res.content))
            if res.text != '""':
                logger.info('exist waiting record with task_uuid={}'.format(res.content))
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def get_material(cls, name):
        params = {'name': name}
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/material/get".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={} result={}'.format(url, res.content))
            return res.json()[0]

    @classmethod
    def get_machine_config(cls, name=None, machine=None):
        """
        get machine config by material name or machine
        :param name: material name or machine
        :return: dict, {}
        """
        params = {}
        if name:
            params['name'] = name
        if machine:
            params['machine'] = machine
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/machine/get".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={}'.format(url))
            return res.json()

    @classmethod
    def post_use(cls, name: str, quantity: int):
        params = {'name': name, 'quantity': quantity}
        url = "{}/coffee/material/use".format(cls.base_url)
        res = requests.post(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def get_formula_composition(cls, formula, cup, formula_in_use=None):
        params = {'formula': formula, 'cup': cup, 'formula_in_use': formula_in_use}
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/composition/get".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        return res.json()

    @classmethod
    def choose_one_speech_text(cls, code):
        params = {'code': code}
        url = "{}/coffee/speech/random".format(cls.base_url)
        try:
            res = requests.get(url, params=params)
            logger.info('url={} params={}, result={}'.format(url, params, res.content))
            return res.content
        except ConnectionError:
            pass

    @classmethod
    def bean_out(cls):
        url = "{}/coffee/material/bean_out".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except ConnectionError:
            pass

    @classmethod
    def bean_reset(cls):
        url = "{}/coffee/material/bean_reset".format(cls.base_url)
        try:
            res = requests.get(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except ConnectionError:
            pass


class ExceptionInterface:
    base_url = module_base_url('exception')

    @classmethod
    def add_error(cls, name, msg):
        try:
            params = {'name': name, 'msg': msg}
            url = "{}/exception/error".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={} params={}, msg={}, result={}'.format(url, params, msg, res.json()))
        except Exception as e:
            logger.error(str(e))

    @classmethod
    def status(cls):
        url = "{}/exception/status".format(cls.base_url)
        res = requests.get(url)
        logger.info('url={}, result={}'.format(url, res.json()))

    @classmethod
    def clear_error(cls, name):
        try:
            params = {'name': name}
            url = "{}/exception/error/clear".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        except Exception as e:
            logger.error(str(e))

    @classmethod
    def add_base_error(cls, arm, code, desc, by, error_status='unsolved'):
        try:
            params = {'arm': arm, 'code': code, 'desc': desc, 'by': by, 'error_status': error_status}
            url = "{}/exception/base_error".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        except Exception as e:
            logger.error(str(e))


class AdamInterface:
    base_url = module_base_url('adam')

    @classmethod
    def prepare_for(cls, formula):
        params = {'formula': formula}
        url = "{}/adam/prepare_for".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def main_make(cls, formula, cup, sweetness, ice, milk):
        params = {'formula': formula, 'cup': cup, 'sweetness': sweetness, 'ice': ice, 'milk': milk}
        url = "{}/adam/main_make".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def make_cold_drink(cls, formula, sweetness, ice, milk, receipt_number):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'receipt_number': receipt_number}
        url = "{}/adam/make_cold_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def make_hot_drink(cls, formula, sweetness, ice, milk, receipt_number):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'receipt_number': receipt_number}
        url = "{}/adam/make_hot_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def make_red_wine(cls, formula, sweetness, ice, milk, receipt_number):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'receipt_number': receipt_number}
        url = "{}/adam/make_red_wine".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def make_white_wine(cls, formula, sweetness, ice, milk, receipt_number):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'receipt_number': receipt_number}
        url = "{}/adam/make_white_wine".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def pour(cls, action):
        params = {'action': action}
        url = "{}/adam/pour".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def standby_pose(cls):
        url = "{}/adam/standby_pose".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def release_ice(cls):
        url = "{}/adam/release_ice".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def inverse(cls, which: define.SUPPORT_ARM_TYPE, pose: adam_schema.Pose, q_pre: dict):
        params = {'which': which}
        json = {'pose': pose, 'q_pre': q_pre}
        url = "{}/kinematics/inverse".format(cls.base_url)
        res = requests.post(url, params=params, json=json)
        logger.info('url={} params={}, json={}, result={}'.format(url, params, json, res.json()))
        return res.content

    @classmethod
    def dance(cls):
        url = "{}/adam/dance".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def change_adam_status(cls, status):
        params = {'status': status}
        url = "{}/adam/change_adam_status".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def random_dance(cls):
        url = "{}/adam/random_dance".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def zero(cls):
        url = "{}/adam/zero".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def stop(cls):
        url = "{}/adam/stop".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def resume(cls):
        url = "{}/adam/resume".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()


class MathadeeInterface:
    base_url = module_base_url('adam')

    @classmethod
    def robot_info(cls, uuid):
        params = {'uuid': uuid}
        url = "{}/matradee/robot/info".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))

    @classmethod
    def robot_task(cls, uuid, position_name):
        params = {'uuid': uuid, 'position_name': position_name}
        url = "{}/matradee/robot/task".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        return res.json()

    @classmethod
    def robot_pos(cls, uuid):
        params = {'uuid': uuid}
        url = "{}/matradee/robot/pos".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, text={}'.format(url, params, res.json()))
        return res.json()


if __name__ == '__main__':
    AudioInterface().gtts('123')
