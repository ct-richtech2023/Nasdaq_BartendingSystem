import datetime
import pytz
import inspect
import json
import math
import os
import shlex
import subprocess

import yaml
from loguru import logger

PROC_1_NAME = None
PCM_NUMBER = None


def get_current_func_name():
    return inspect.stack()[1][3]


def get_file_dir_name(abs_path):
    abs_path = os.path.abspath(abs_path)
    dir_path = os.path.dirname(abs_path)
    return os.path.basename(dir_path)


def read_yaml(path):
    with open(path, encoding="utf-8") as f:
        result = f.read()
        result = yaml.load(result, Loader=yaml.FullLoader)
        return result


def read_resource_json(path) -> dict:
    path = '/richtech/resource' + path
    assert os.path.isfile(path), '{} is not exist'.format(path)
    with open(path, encoding="utf-8") as f:
        result = f.read()
        return json.loads(result)


def write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=yaml.SafeDumper)


def get_execute_cmd_result(cmd: str, shell=False, **kwargs):
    cmd_err = "execute cmd='{}' failed".format(cmd)
    args = cmd if shell else shlex.split(cmd)
    logger.info("cmd={}, shell={}, args={}".format(cmd, shell, args))
    try:
        res = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True,
                                      shell=shell, encoding="utf-8", **kwargs)
    except subprocess.TimeoutExpired:
        err = "{}, timeout={} seconds".format(cmd_err, kwargs.get('timeout'))
        logger.error(err)
        raise Exception(err)
    except subprocess.CalledProcessError as e:
        err = "{}, code={}, err={}".format(cmd_err, e.returncode, e.output.strip())
        logger.error(err)
        raise Exception(err)
    except Exception as e:
        err = "{}, err={}".format(cmd_err, str(e))
        logger.error(err)
        raise Exception(err)
    else:
        msg = "cmd={}, return_code=0".format(cmd)
        logger.debug(msg)
        # return bytes.decode(p).strip()
        return res


def get_now_day():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_now_day_now_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_proc_head_1_name():
    """
    output like: "systemd" or "supervisord"
    """
    global PROC_1_NAME
    if PROC_1_NAME is None:
        cmd = "cat /proc/1/status | head -1"
        result = get_execute_cmd_result(cmd, shell=True)
        proc_name = result.strip().split(':')[-1]
        PROC_1_NAME = proc_name.strip()
        logger.info("current system No.1 proc is '{}'".format(PROC_1_NAME))
    return PROC_1_NAME


def compare_value(a, b, abs_tol=1e-5):
    # 比较两个对象中的值是否相似
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for i in range(len(a)):
            flag = compare_value(a[i], b[i], abs_tol=abs_tol)
            if not flag:
                return False
        else:
            return True
    elif isinstance(a, list) and not isinstance(b, list):
        return False
    elif not isinstance(a, list) and isinstance(b, list):
        return False
    else:
        if type(a) not in [int, float] or type(b) not in [int, float]:
            return False
        return math.isclose(a, b, abs_tol=abs_tol)


# def utc_to_local(local_tz: str, utc_time: str, fmt='%Y-%m-%d %H:%M:%S'):
#     utc_time = datetime.datetime.strptime(utc_time, fmt)
#     utc_tz = pytz.timezone('UTC')
#     utc_time = utc_tz.localize(utc_time)
#
#     local_tz = pytz.timezone(local_tz)
#     format_time = utc_time.astimezone(local_tz)
#     return format_time.strftime(fmt)
#
#
# def local_to_utc(local_tz: str, origin_time: str, fmt='%Y-%m-%d %H:%M:%S'):
#     origin_time = datetime.datetime.strptime(origin_time, fmt)
#     origin_tz = pytz.timezone(local_tz)
#     origin_time = origin_tz.localize(origin_time)
#     # print(origin_time.strftime(fmt))
#
#     utc_tz = pytz.timezone('UTC')
#     format_time = origin_time.astimezone(utc_tz)
#     return format_time.strftime(fmt)


def utc_to_local(local_offset: int, utc_time: str, fmt='%Y-%m-%d %H:%M:%S'):
    utc_time = datetime.datetime.strptime(utc_time, fmt)
    format_time = utc_time + datetime.timedelta(hours=local_offset)
    return format_time.strftime(fmt)


def local_to_utc(local_offset: int, origin_time: str, fmt='%Y-%m-%d %H:%M:%S'):
    origin_time = datetime.datetime.strptime(origin_time, fmt)
    format_time = origin_time + datetime.timedelta(hours=0 - local_offset)
    return format_time.strftime(fmt)


def format_option(ori_name):
    if ori_name == 'no':
        return 'no_ice'
    if ori_name == 'Med':
        return 'Medium Cup'
    if ori_name == 'Lrg':
        return 'Large Cup'
    return ori_name
