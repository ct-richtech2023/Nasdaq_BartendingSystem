from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

# kai he
left = {
    "a": {
        "x": 450,
        "y": 360,
        "z": 750,
        "roll": 0,
        "pitch": -30,
        "yaw": -90
    },
    "b": {
        "x": 450,
        "y": 160,
        "z": 750,
        "roll": 0,
        "pitch": 30,
        "yaw": -90
    }
}

import requests


def func(value_dict: dict):
    requests.post(url="http://127.0.0.1:9003/adam/position?which={}".format(value_dict.get('which')),
                  json=value_dict.get('value'))


for i in range(5):
    for value in left.values():
        with ThreadPoolExecutor(max_workers=8) as pool:
            temp1 = deepcopy(value)
            temp2 = deepcopy(value)

            temp2['y'] = -temp2['y']
            temp2['yaw'] = -temp2['yaw']
            value_dict = (
                {"which": 'left', 'value': temp1}, {"which": 'right', 'value': temp2},
            )

            results = pool.map(func, (value_dict))
            for r in results:
                pass

lashen1 = {
    "left": {
        "x": 500,
        "y": -100,
        "z": 500,
        "roll": 90,
        "pitch": 90,
        "yaw": 0
    },
    "right": {
        "x": 500,
        "y": -400,
        "z": 500,
        "roll": -45,
        "pitch": 90,
        "yaw": 0
    }
}

lashen2 = {
    "left": {
        "x": 500,
        "y": -150,
        "z": 500,
        "roll": 90,
        "pitch": 90,
        "yaw": 0
    },
    "right": {
        "x": 500,
        "y": -450,
        "z": 500,
        "roll": -45,
        "pitch": 90,
        "yaw": 0
    }
}


for i in range(4):
    with ThreadPoolExecutor(max_workers=2) as pool:
        value_dict = (
            {"which": 'left', 'value': lashen1['left']}, {"which": 'right', 'value': lashen1['right']},
        )

        results = pool.map(func, (value_dict))
        for r in results:
            pass
    with ThreadPoolExecutor(max_workers=2) as pool:
        value_dict = (
            {"which": 'left', 'value': lashen2['left']}, {"which": 'right', 'value': lashen2['right']},
        )

        results = pool.map(func, (value_dict))
        for r in results:
            pass


lashen2 = {
    "left": {
        "x": 500,
        "y": 450,
        "z": 500,
        "roll": 45,
        "pitch": 90,
        "yaw": 0
    },
    "right": {
        "x": 500,
        "y": 150,
        "z": 500,
        "roll": -90,
        "pitch": 90,
        "yaw": 0,
    }
}


for i in range(4):
    with ThreadPoolExecutor(max_workers=2) as pool:
        value_dict = (
            {"which": 'left', 'value': lashen1['left']}, {"which": 'right', 'value': lashen1['right']},
        )

        results = pool.map(func, (value_dict))
        for r in results:
            pass
    with ThreadPoolExecutor(max_workers=2) as pool:
        value_dict = (
            {"which": 'left', 'value': lashen2['left']}, {"which": 'right', 'value': lashen2['right']},
        )

        results = pool.map(func, (value_dict))
        for r in results:
            pass