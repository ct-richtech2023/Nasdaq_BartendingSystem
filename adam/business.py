import math
import os
import random
import threading
import time
import csv
import traceback
import serial
from copy import deepcopy
from typing import Literal

from loguru import logger

from xarm.wrapper import XArmAPI

from common import define, utils, conf
from common.api import ExceptionInterface, AudioInterface, CoffeeInterface
from common.define import ExceptionType, Arm, AdamTaskStatus, audio_dir
from common.schemas import adam as adam_schema
from common.schemas import common as common_schema
from common.schemas import total as total_schema
from common.db.crud import adam as adam_crud
from common.myerror import MoveError, FormulaError, MaterialError, CoffeeError
from init import EnvConfig
from back import RecordThread
from devices.coffee.coffee import CoffeeDriver
from devices.coffee.constant import MachineStatus as CoffeeMachineStatus, COFFEE_STATUS
from devices.conveyer import TakeConveyer, Conveyer
from devices.arduino import AdamOneArduino


def get_adam_obj():
    """
    Adam对象只创建一次
    """
    if not Adam.Instance:
        Adam.Instance = Adam()
    return Adam.Instance


class Adam:
    Instance = None

    def __init__(self):
        # adam所处环境的配置
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())
        # adam机器人本身的配置
        self.adam_config = adam_schema.AdamConfig(**conf.get_adam_config())
        self.env = EnvConfig(self.machine_config, self.adam_config)
        self.left, self.right = self.env.left, self.env.right
        self.cup_count = 0

        adam_crud.init_tap()

        # try:
        #     pass
        #     #self.coffee_driver = CoffeeDriver('/dev/ttyUSB0')
        #     #self.coffee_status = self.coffee_driver.last_status
        # except Exception as e:
        #     AudioInterface.gtts(str(e))
        #     logger.error(str(e))
        #     exit(-1)

        self.task_status = None

        # 程序上电就会强制回零点
        self.check_adam_goto_initial_position()
        # task_status表示adam的状态
        self.task_status = AdamTaskStatus.idle
        self.cup_env = self.env.machine_config.cup_env
        self.current_cup_name = define.CupName.hot_cup
        self.ice_num = 0

        self.pump_1 = 'A'
        self.pump_2 = 'B'
        self.pump_3 = 'C'
        self.pump_4 = 'D'
        self.pump_5 = 'E'
        self.pump_6 = 'F'
        self.pump_7 = 'G'
        self.pump_8 = 'H'
        self.pump_9 = 'J'
        self.pump_10 = 'K'
        self.washer_valve = 'L'

        self.pump_1_off = 'a'
        self.pump_2_off = 'b'
        self.pump_3_off = 'c'
        self.pump_4_off = 'd'
        self.pump_5_off = 'e'
        self.pump_6_off = 'f'
        self.pump_7_off = 'g'
        self.pump_8_off = 'h'
        self.pump_9_off = 'j'
        self.pump_10_off = 'k'
        self.washer_valve_off = 'l'

        self.all_pumps = 'I'
        self.all_pumps_off = 'i'

        self.left_record = RecordThread(self.left, self.env.get_record_path('left'), 'left arm')
        self.right_record = RecordThread(self.right, self.env.get_record_path('right'), 'right arm')
        self.left_roll_end = True
        self.right_roll_end = True
        self.init_record()
        self.thread_lock = threading.Lock()

        # self.coffee_thread = QueeyCoffeeThread(self.coffee_driver)
        # self.coffee_thread.setDaemon(True)
        # self.coffee_thread.start()
        # self.warm_up()

        self.left_is_use = False
        self.right_is_use = False
        self.waiting_Over_Gold = False
        self.waiting_Rowdy_IPA = False

        self.is_coffee_finished = False

        AudioInterface.gtts('/richtech/resource/audio/voices/ready.mp3')

    def init_record(self):
        """
        init record thread
        pause until get an order
        """
        self.left_record.setDaemon(True)
        self.right_record.setDaemon(True)
        self.left_record.clear()
        self.right_record.clear()
        self.left_record.start()
        self.left_record.pause()
        self.right_record.start()
        self.right_record.pause()

    def test_arduino(self, char):
        self.arduino.arduino.open()
        self.arduino.arduino.send_one_msg(char)
        self.arduino.arduino.close()

    # left actions
    def take_hot_cup(self):
        """
        左手取热咖杯子，一旦取杯子就认为开始做咖啡了
        """
        logger.info('take_hot_cup')
        pose_speed = 200

        self.change_adam_status(AdamTaskStatus.making)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        self.current_cup_name = cup_config.name
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)
        which = Arm.left

        def take_cup():
            # 计算旋转手臂到落杯器的角度
            cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)
            up_take_pose = deepcopy(cup_pose)
            up_take_pose.z = 250
            # up_take_pose.y += 200
            logger.info("distance is {}".format(up_take_pose.y))
            self.goto_initial_position_direction(which, 0, wait=False, speed=400)
            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 先张开夹爪
            self.goto_point(which, up_take_pose, speed=pose_speed, wait=False)  # 运动到抓杯位置上方
            self.goto_tool_position(which, yaw=180, speed=1500, wait=True)  # 翻转夹爪
            self.goto_temp_point(which, z=cup_pose.z, speed=pose_speed, wait=False)  # 运动到抓杯位置
            self.goto_gripper_position(which, cup_config.clamp, wait=True)  # 闭合夹爪
            logger.info('take cup with clamp = {}'.format(cup_config.clamp))
            self.env.one_arm(which).set_collision_sensitivity(cup_config.collision_sensitivity)  # 设置灵敏度，根据实际效果确定是否要注释
            self.safe_set_state(Arm.left, 0)
            time.sleep(0.1)
            self.goto_temp_point(which, z=up_take_pose.z + 20, speed=pose_speed, wait=False)  # 向上拔杯子
            CoffeeInterface.post_use(define.CupName.hot_cup, 1)  # 热咖杯子数量-1
            self.goto_tool_position(which, yaw=-180, speed=1500, wait=True)  # 再次翻转夹爪
            # self.goto_temp_point(which, x=up_take_pose.x + 5, y=up_take_pose.y - 165, speed=pose_speed, wait=False)
            # self.goto_temp_point(which, z=up_take_pose.z - 100, speed=pose_speed, wait=True)
            # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)
            self.safe_set_state(Arm.left, 0)
            time.sleep(0.1)
            #  todo 运动到arduino检测位置

        take_cup()
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)
        # try:
        #     while not self.arduino.check_cup_token(self.current_cup_name, 400):
        #         cup_config.clamp -= 3
        #         take_cup()
        #     # self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)  # 运动回零点
        # except Exception as e:
        #     self.stop()

    def take_daily_coffee(self):

        pose_speed = 300  # 800
        americano_pose = deepcopy(self.env.machine_config.americano.pose)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.left
        # 咖啡机出口高度 - （杯子高度 - 夹爪抓杯高度）-3cm
        # americano_pose.z += 160 #americano_pose.z - (cup_config.high - cup_config.pose.z) - 30
        # americano_pose.x += 20
        americano_pose.roll = self.get_xy_initial_angle(which, americano_pose.x, americano_pose.y)

        self.goto_initial_position_direction(which, americano_pose.roll, wait=True, speed=pose_speed)  # 运动回零点，朝向咖啡机方向
        self.goto_gripper_position(which, 470, wait=True)
        temp_pose = deepcopy(americano_pose)
        temp_pose.y -= 100
        self.goto_point(which, temp_pose, wait=True, speed=pose_speed)

        self.goto_point(which, americano_pose, wait=True, speed=pose_speed)
        time.sleep(6)
        self.goto_temp_point(which, y=americano_pose.y - 100, wait=True, speed=pose_speed)  # 做完咖啡回退，准备接糖浆等配料
        self.goto_initial_position_direction(which, americano_pose.roll, wait=True, speed=pose_speed)
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def take_coffee_machine_demo(self):
        """
        "coffee": {
            "count": 60,
            "coffee_make": {"drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
                        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
                        "coffeeMilkTogether": 0, "adjustOrder": 1}
            }
        """
        pose_speed = 800  # 800
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.left
        # 咖啡机出口高度 - （杯子高度 - 夹爪抓杯高度）-3cm
        coffee_pose.z = coffee_pose.z - (cup_config.high - cup_config.pose.z) - 30
        coffee_pose.x += 20
        coffee_pose.roll = self.get_xy_initial_angle(which, coffee_pose.x, coffee_pose.y)

        self.goto_initial_position_direction(which, coffee_pose.roll, wait=False, speed=pose_speed)  # 运动回零点，朝向咖啡机方向
        self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
        formula = 'espresso'
        try:
            composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
            coffee_machine = composition.get('coffee_machine', {})
            for name, config in coffee_machine.items():
                adam.coffee_driver.make_coffee_from_dict(config.get('coffee_make'))
        except MoveError as e:
            return JSONResponse(status_code=510, content={'error': str(e)})

        time.sleep(3)
        self.goto_temp_point(which, x=coffee_pose.x - 300, wait=False, speed=pose_speed)  # 做完咖啡回退，准备接糖浆等配料

    def take_coffee_machine_espresso(self):
        """
        "coffee": {
            "count": 60,
            "coffee_make": {"drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
                        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
                        "coffeeMilkTogether": 0, "adjustOrder": 1}
            }
        """
        pose_speed = 200  # 800
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.left
        # 咖啡机出口高度 - （杯子高度 - 夹爪抓杯高度）-3cm
        coffee_pose.z = coffee_pose.z - (cup_config.high - cup_config.pose.z) - 30
        coffee_pose.roll = self.get_xy_initial_angle(which, coffee_pose.x, coffee_pose.y)

        # self.goto_initial_position_direction(which, coffee_pose.roll, wait=False, speed=pose_speed)  # 运动回零点，朝向咖啡机方向
        self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
        try:
            if self.coffee_driver.query_status().get('system_status') != CoffeeMachineStatus.idle:
                # 制作前检查咖啡机状态,必须为idle
                raise CoffeeError('Sorry coffee machine is not prepared, status is {}'.format(
                    self.coffee_driver.query_status()))
            # logger.debug('coffee_make = {}'.format(composition.get('coffee').get('coffee_make')))
            self.coffee_driver.make_coffee('espresso', 600)  # 600 for cappucino 200 for cold latte
            while status_msg := self.coffee_driver.query_status():
                status = status_msg.get('system_status')
                error_msg = status_msg.get('error_msg', [])
                # 制作过程中，如果不是making状态就退出循环，否则一直等待
                if status != CoffeeMachineStatus.making:
                    break
                # 制作过程中有报错信息，立刻抛出异常
                if error_msg:
                    raise Exception('make error! status_msg={}'.format(status_msg))
                time.sleep(1)
            if self.coffee_driver.query_status().get('system_status') != CoffeeMachineStatus.idle:
                # 制作完成后，咖啡机必须为idle状态
                raise CoffeeError('Sorry coffee making failed, status is {}'.format(
                    self.coffee_driver.query_status()))
            # CoffeeInterface.post_use('coffee', composition.get('coffee').get('coffee_make').get('volume'))
        except Exception as e:
            raise e
            raise CoffeeError(str(e))

    def take_ingredients_chocolate(self):
        """
        接糖浆等配料，左手拿杯子就左手去接，右手拿杯子就右手去接
        """
        pose_speed = 300  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        take_pose = deepcopy(tap_pose)
        take_pose.z = 155  # 龙头下方位置
        take_pose.y += 10
        open_dict = {}  # {'tap_0': 150} arduino打开水泵需要字段
        first_run_flag = True
        self.thread_lock.acquire()
        if first_run_flag:
            self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 运动到龙头下方位置
            self.goto_temp_point(which, x=take_pose.x + 20, speed=pose_speed, wait=True)  # 向上运动，准备接各种配料
            char = "g"
            if not ser.isOpen():
                ser.open()
                time.sleep(1)
            ser.write(char.encode('utf-8'))
            logger.info('sent {}'.format(char))
            time.sleep(5)
            ser.write(char.encode('utf-8'))

            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            first_run_flag = False
            # machine_config = CoffeeInterface.get_machine_config(name)
            # machine_name = '{}_{}'.format(machine_config.get('machine'), machine_config.get('num'))
            # open_dict[machine_name] = quantity
            # logger.info('prepare open {} for {} ml'.format(machine_name, quantity))
            # logger.debug('arduino open_dict = {}'.format(open_dict))
            # CoffeeInterface.post_use(name, quantity)
        # self.arduino.open_port(open_dict) # todo 控制arduino打开接奶，以实际测试为准
        time.sleep(2)  # 模拟等待接配料时间
        if not first_run_flag:  # 机械臂有动作
            # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 运动回零点
            pass
        self.thread_lock.release()

    def take_ingredients_syrup(self):
        """
        接糖浆等配料，左手拿杯子就左手去接，右手拿杯子就右手去接
        """
        pose_speed = 300  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        take_pose = deepcopy(tap_pose)
        take_pose.z = 155  # 龙头下方位置
        take_pose.y += 10
        open_dict = {}  # {'tap_0': 150} arduino打开水泵需要字段
        first_run_flag = True
        self.thread_lock.acquire()
        if first_run_flag:
            self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 运动到龙头下方位置
            self.goto_temp_point(which, x=take_pose.x + 20, speed=pose_speed, wait=True)  # 向上运动，准备接各种配料
            char = "f"
            if not ser.isOpen():
                ser.open()
                time.sleep(1)
            ser.write(char.encode('utf-8'))
            logger.info('sent {}'.format(char))
            time.sleep(5)
            ser.write(char.encode('utf-8'))

            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            first_run_flag = False
            # machine_config = CoffeeInterface.get_machine_config(name)
            # machine_name = '{}_{}'.format(machine_config.get('machine'), machine_config.get('num'))
            # open_dict[machine_name] = quantity
            # logger.info('prepare open {} for {} ml'.format(machine_name, quantity))
            # logger.debug('arduino open_dict = {}'.format(open_dict))
            # CoffeeInterface.post_use(name, quantity)
        # self.arduino.open_port(open_dict) # todo 控制arduino打开接奶，以实际测试为准
        time.sleep(2)  # 模拟等待接配料时间
        if not first_run_flag:  # 机械臂有动作
            # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 运动回零点
            pass
        self.thread_lock.release()

    def moveto_packup_position(self):
        self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([27.1, -101.2, 5, -0.7, 94.0, -3.1]), wait=False)
        self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-27.2, -110.5, 9.0, 2.9, 102.5, 9.0]), wait=False)

    def rotate_take_cup(self):
        e = 'hello'
        # AudioInterface.gtts(str(e))
        # AudioInterface.gtts('/richtech/resource/audio/voices/f1_cosmo.mp3')

        self.cup_count += 1
        logger.debug('rotate {}'.format(self.cup_count))
        which = Arm.right

        self.goto_gripper_position(which, 350, wait=True)

        self.goto_blockly_point(which, points=[315.0, -362.7, 284.3, 73.7, 86.4, 74.0], wait=False, speed=300)  # 运动到龙头下方位置

        if self.cup_count in [1, 6, 11]:
            self.goto_blockly_point(which, points=[268.8, -658.4, 95.4, -108.0, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
            if self.cup_count == 1:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 160, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 6:
                current_position = self.current_position(Arm.right)  # plus 115
                self.goto_temp_point(which, y=current_position.y - 275, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 11:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 390, speed=600, wait=True)  # 向上运动，准备接各种配料


        elif self.cup_count in [2, 7, 12]:
            self.goto_blockly_point(which, points=[150.7, -662.3, 99.7, -108.0, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
            if self.cup_count == 2:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 160, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 7:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 275, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 12:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 390, speed=600, wait=True)  # 向上运动，准备接各种配料


        elif self.cup_count in [3, 8, 13]:
            self.goto_blockly_point(which, points=[29.2, -666.4, 104.1, -108.0, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
            if self.cup_count == 3:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 160, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 8:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 275, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 13:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 390, speed=600, wait=True)  # 向上运动，准备接各种配料


        elif self.cup_count in [4, 9, 14]:
            self.goto_blockly_point(which, points=[-87.9, -670.3, 108.4, -108.0, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
            if self.cup_count == 4:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 160, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 9:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 275, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 14:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 390, speed=600, wait=True)  # 向上运动，准备接各种配料

        elif self.cup_count in [5, 10, 15]:
            self.goto_blockly_point(which, points=[-209.1, -674.4, 112.8, -108.0, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
            if self.cup_count == 5:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 160, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 10:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 275, speed=600, wait=True)  # 向上运动，准备接各种配料
            if self.cup_count == 15:
                current_position = self.current_position(Arm.right)
                self.goto_temp_point(which, y=current_position.y - 390, speed=600, wait=True)  # 向上运动，准备接各种配料

        current_position = self.current_position(Arm.right)
        self.goto_temp_point(which, z=current_position.z + 220, speed=600, wait=True)  # 向上运动，准备接各种配料
        self.goto_blockly_point(which, points=[269.2, -538.5, 232.8, 171.4, 87.8, 163.9], wait=True, speed=300)  # 运动到龙头下方位置
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -32.3, 327.9, 40.3, 88.2, 90.0]), wait=True, speed=300)

        if self.cup_count == 15:
            self.cup_count = 0

    def make_double_beer(self, sweetness):
        for i in range(sweetness):
            def left_action():
                self.make_beer(Arm.left)

            def right_action():
                self.make_beer(Arm.right)

            thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

            pass

    def make_beer(self, which):
        TCP_speed = 400
        angle_speed = 300

        if which == Arm.left:
            self.goto_gripper_position(Arm.left, 700, wait=False)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([209.4, -22.6, -39.0, -90.3, 89.5, 28.3]), wait=False, speed=angle_speed)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([155.0, -13.9, -82.3, -81.2, 35.5, 171.3]), wait=False, speed=angle_speed)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([565.5, 814.4, 132.5, -88.7, -87.9, -91.3]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.left, 0, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([580.7, 816.7, 251.5, -89.0, -87.9, -90.9]), wait=False, speed=TCP_speed)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([150.4, 55.3, -96.8, -88.1, 21.0, 20.5]), wait=False, speed=angle_speed)
            self.goto_gripper_position(Arm.left, 500, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([672.8, 74.7, 100.9, 45.0, 90.0, 0.0]), wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.left, 850, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([672.8, 74.7, 175.3, 45.0, 90.0, 0.0]), wait=False, speed=400)
            self.goto_gripper_position(Arm.left, 1, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([688.9, 74.7, 153.7, 45.0, 90.0, 0.0]), wait=False, speed=400)
            time.sleep(2)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([672.8, 74.7, 175.3, 45.0, 90.0, 0.0]), wait=False, speed=400)
            self.goto_gripper_position(Arm.left, 850, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([672.8, 74.7, 100.9, 45.0, 90.0, 0.0]), wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.left, 500, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([672.1, 73.7, 245.9, 45.0, 90.0, 0.0]), wait=False, speed=275)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([789.5, 342.4, 245.9, 0.0, 90.0, 0.0]), wait=False, speed=275)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([789.5, 342.4, 117.1, 0.0, 90.0, 0.0]), wait=False, speed=275)
            self.goto_gripper_position(Arm.left, 850, wait=False)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([567.0, 342.4, 117.1, 0.0, 90.0, 0.0]), wait=False, speed=275)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([209.4, -22.6, -39.0, -90.3, 89.5, 28.3]), wait=True, speed=275)
        elif which == Arm.right:
            self.goto_gripper_position(Arm.right, 700, wait=True)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-163.7, 1.4, -99.6, 81.6, 44.3, -168.9]), wait=False, speed=angle_speed)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([585.8, -821.4, 120.3, 89.7, -89.4, 90.2]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 0, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([585.8, -821.4, 260.7, 89.7, -89.4, 90.2]), wait=True, speed=TCP_speed)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-150.0, 56.5, -97.3, 90.2, 20.7, -22.5]), wait=False, speed=angle_speed)
            self.goto_gripper_position(Arm.right, 500, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 98.2, 135.0, 90.0, 180.0]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 176.0, -45.0, 90.0, 0.0]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 1, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 153.8, -45.0, 90.0, 0.0]), wait=True, speed=TCP_speed)
            time.sleep(2)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 176.0, -45.0, 90.0, 0.0]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 98.2, 135.0, 90.0, 180.0]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 500, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.1, -63.1, 245.0, 135.0, 90.0, 180.0]), wait=False, speed=TCP_speed)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([758.1, -234.1, 235.9, -139.3, 90.0, -132.2]), wait=False, speed=TCP_speed)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([758.1, -234.1, 117.8, 40.7, 90.0, 47.8]), wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_point(Arm.right, common_schema.Pose.list_to_obj([570.0, -257.5, 117.8, 141.0, 90.0, 148.1]), wait=False, speed=TCP_speed)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=True, speed=angle_speed)

    # All of the September Soccer event functions
    def make_rotating_beers(self, formula):
        TCP_speed = 400
        angle_speed = 300
        dispense_speed = 200

        left_put_cup_pose = deepcopy(self.env.machine_config.put_left.pose)
        left_put_cup_pose.roll = self.get_xy_initial_angle(Arm.left, left_put_cup_pose.x, left_put_cup_pose.y)

        right_put_cup_pose = deepcopy(self.env.machine_config.put_right.pose)
        right_put_cup_pose.roll = self.get_xy_initial_angle(Arm.right, right_put_cup_pose.x, right_put_cup_pose.y)

        if formula == "Double Beer A":
            # Thread for taking both cups at the same time
            left_beer_pose = deepcopy(self.env.machine_config.left_beer_a.pose)
            left_beer_pose.roll = self.get_xy_initial_angle(Arm.left, left_beer_pose.x, left_beer_pose.y)

            right_beer_pose = deepcopy(self.env.machine_config.beer_a.pose)
            right_beer_pose.roll = self.get_xy_initial_angle(Arm.right, right_beer_pose.x, right_beer_pose.y)
        elif formula == "Double Beer B":
            left_beer_pose = deepcopy(self.env.machine_config.left_beer_b.pose)
            left_beer_pose.roll = self.get_xy_initial_angle(Arm.left, left_beer_pose.x, left_beer_pose.y)

            right_beer_pose = deepcopy(self.env.machine_config.beer_b.pose)
            right_beer_pose.roll = self.get_xy_initial_angle(Arm.right, right_beer_pose.x, right_beer_pose.y)

        def left_step_1():
            cup_config = self.get_cup_config(define.CupName.left_cup)
            self.current_cup_name = cup_config.name
            logger.info('now take {} cup'.format(cup_config.name))
            cup_pose = deepcopy(cup_config.pose)
            cup_pose.roll = self.get_xy_initial_angle(Arm.left, cup_pose.x, cup_pose.y)
            # Grab the cup
            self.goto_gripper_position(Arm.left, 850, wait=True)
            self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=TCP_speed)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([185.4, -16.8, -53, -139.8, 88, -148.6]), wait=True, speed=angle_speed)
            self.goto_temp_point(Arm.left, x=cup_pose.x, y=cup_pose.y, z=cup_pose.z, wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.left, cup_config.clamp, wait=True)
            self.goto_temp_point(Arm.left, z=cup_pose.z + 200, wait=False, speed=TCP_speed)
            self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([180.2, 10.7, -72.4, -53.7, 49.8, 2.2]), wait=False, speed=angle_speed)
            # pass
            # Take cup
            # Take beer from tap and raise back up
            # Place cup
            # Move back to zero position/standby

        def right_step_1():
            cup_config = self.get_cup_config(define.CupName.right_cup)
            self.current_cup_name = cup_config.name
            logger.info('now take {} cup'.format(cup_config.name))
            cup_pose = deepcopy(cup_config.pose)
            cup_pose.roll = self.get_xy_initial_angle(Arm.right, cup_pose.x, cup_pose.y)
            # Grab the cup
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=TCP_speed)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-196.6, -22.8, -58.7, 114.6, 81.1, 166.8]), wait=True, speed=angle_speed)
            self.goto_temp_point(Arm.right, x=cup_pose.x, y=cup_pose.y, z=cup_pose.z, wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, cup_config.clamp, wait=True)
            self.goto_temp_point(Arm.right, z=cup_pose.z + 200, wait=False, speed=TCP_speed)
            self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-174.3, 13.4, -60.5, 56, 36.9, -7.6]), wait=False, speed=angle_speed)
            # pass
            # Take cup
            # Go to waiting position
            ### Sleep ###
            # Take beer from tap and raise back up
            # Place cup and go to zero/standby

        thread_list = [threading.Thread(target=left_step_1), threading.Thread(target=right_step_1)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        # Move to beer dispensor
        keep_height = deepcopy(left_beer_pose)
        keep_height.z = 135
        self.goto_point(Arm.left, keep_height, wait=True, speed=TCP_speed)
        self.goto_temp_point(Arm.left, z=left_beer_pose.z, wait=True, speed=dispense_speed)
        self.goto_gripper_position(Arm.left, 850, wait=True)
        self.goto_temp_point(Arm.left, z=left_beer_pose.z + 125, wait=False, speed=TCP_speed)
        self.goto_temp_point(Arm.left, x=left_beer_pose.x + 100, y=left_beer_pose.y - 100, wait=True, speed=TCP_speed)
        # Pushes the cup down onto the dispensor
        self.goto_temp_point(Arm.left, z=left_beer_pose.z + 67, wait=True, speed=dispense_speed)
        self.goto_temp_point(Arm.left, x=left_beer_pose.x, y=left_beer_pose.y, z=left_beer_pose.z + 125, wait=False, speed=TCP_speed)
        self.goto_temp_point(Arm.left, z=left_beer_pose.z, wait=True, speed=TCP_speed)
        self.goto_gripper_position(Arm.left, 450, wait=True)
        # Picks the cup back up
        time.sleep(10)
        self.goto_temp_point(Arm.left, z=left_beer_pose.z + 125, wait=True, speed=dispense_speed)
        # Puts cup down
        self.goto_point(Arm.left, left_put_cup_pose, wait=False, speed=275)

        def left_final_step():
            self.goto_temp_point(Arm.left, z=left_put_cup_pose.z - 128, wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.left, 850, wait=True)
            self.goto_temp_point(Arm.left, x=left_put_cup_pose.x - 122, z=left_put_cup_pose.z - 128, wait=False, speed=TCP_speed)
            self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=TCP_speed)

        def right_final_step():
            # Move to beer dispensor
            keep_height = deepcopy(right_beer_pose)
            keep_height.z = 135
            self.goto_point(Arm.right, keep_height, wait=True, speed=TCP_speed)
            self.goto_temp_point(Arm.right, z=right_beer_pose.z, wait=True, speed=dispense_speed)
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_temp_point(Arm.right, z=right_beer_pose.z + 125, wait=False, speed=TCP_speed)
            self.goto_temp_point(Arm.right, x=right_beer_pose.x + 100, y=right_beer_pose.y + 100, wait=True, speed=TCP_speed)
            # Pushes the cup down onto the dispensor
            self.goto_temp_point(Arm.right, z=right_beer_pose.z + 70, wait=True, speed=dispense_speed)
            self.goto_temp_point(Arm.right, x=right_beer_pose.x, y=right_beer_pose.y, z=right_beer_pose.z + 125, wait=False, speed=TCP_speed)
            self.goto_temp_point(Arm.right, z=right_beer_pose.z, wait=True, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 450, wait=True)
            # Picks the cup back up
            time.sleep(10)
            self.goto_temp_point(Arm.right, z=right_beer_pose.z + 125, wait=True, speed=dispense_speed)
            # Puts cup down
            self.goto_point(Arm.right, right_put_cup_pose, wait=True, speed=275)
            self.goto_temp_point(Arm.right, z=right_put_cup_pose.z - 128, wait=False, speed=TCP_speed)
            self.goto_gripper_position(Arm.right, 850, wait=True)
            self.goto_temp_point(Arm.right, x=right_put_cup_pose.x - 122, z=right_put_cup_pose.z - 128, wait=False, speed=TCP_speed)
            self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=TCP_speed)

        thread_list2 = [threading.Thread(target=left_final_step), threading.Thread(target=right_final_step)]
        for t in thread_list2:
            t.start()
        for t in thread_list2:
            t.join()

        # TCP_speed = 400
        # angle_speed = 300
        # logger.info("Now making the beer order")
        # logger.info("which is {}========================".format(which))

        # if which == Arm.left:
        #     if formula == "Beer A":
        #         beer_pose = deepcopy(self.env.machine_config.left_beer_a.pose)
        #     else:
        #         beer_pose = deepcopy(self.env.machine_config.left_beer_b.pose)
        #     beer_pose.roll = self.get_xy_initial_angle(which, beer_pose.x, beer_pose.y)

        #     cup_config = self.get_cup_config(define.CupName.left_cup)
        #     self.current_cup_name = cup_config.name
        #     logger.info('now take {} cup'.format(cup_config.name))
        #     cup_pose = deepcopy(cup_config.pose)
        #     cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)

        #     put_cup_pose = deepcopy(self.env.machine_config.put_left.pose)
        #     put_cup_pose.roll = self.get_xy_initial_angle(which, put_cup_pose.x, put_cup_pose.y)
        #     #Grab the cup
        #     self.goto_gripper_position(which, 850, wait=True)
        #     self.goto_angles(which, adam_schema.Angles.list_to_obj([185.4, -16.8, -53, -139.8, 88, -148.6]), wait=True, speed = angle_speed)
        #     self.goto_temp_point(which, x=cup_pose.x, y=cup_pose.y, z=cup_pose.z, wait=False, speed=TCP_speed)
        #     self.goto_gripper_position(which, cup_config.clamp, wait=True)
        #     self.goto_temp_point(which, z=cup_pose.z + 200, wait=False, speed=TCP_speed)
        #     self.goto_angles(which, adam_schema.Angles.list_to_obj([174.2, 22.9, -74.3, -63.1, 40.2, 10.8]), wait=False, speed = angle_speed)            

        # elif which == Arm.right:
        #     if formula == "Beer A":
        #         beer_pose = deepcopy(self.env.machine_config.beer_a.pose)
        #     else:
        #         beer_pose = deepcopy(self.env.machine_config.beer_b.pose)
        #     beer_pose.roll = self.get_xy_initial_angle(which, beer_pose.x, beer_pose.y)
        #     cup_config = self.get_cup_config(define.CupName.right_cup)
        #     self.current_cup_name = cup_config.name
        #     logger.info('now take {} cup'.format(cup_config.name))
        #     cup_pose = deepcopy(cup_config.pose)
        #     cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)

        #     put_cup_pose = deepcopy(self.env.machine_config.put_right.pose)
        #     put_cup_pose.roll = self.get_xy_initial_angle(which, put_cup_pose.x, put_cup_pose.y)
        #     #Grab the cup
        #     self.goto_gripper_position(which, 850, wait=True)
        #     self.goto_angles(which, adam_schema.Angles.list_to_obj([-196.6, -22.8, -58.7, 114.6, 81.1, 166.8]), wait=True, speed = angle_speed)
        #     self.goto_temp_point(which, x=cup_pose.x, y=cup_pose.y, z=cup_pose.z, wait=False, speed=TCP_speed)
        #     self.goto_gripper_position(which, cup_config.clamp, wait=True)
        #     self.goto_temp_point(which, z=cup_pose.z + 200, wait=False, speed=TCP_speed)
        #     self.goto_angles(which, adam_schema.Angles.list_to_obj([-174.3, 13.4, -60.5, 56, 36.9, -7.6]), wait=False, speed = angle_speed)

        # else:
        #     pass
        # #Check if the other arm is going to the same beer dispensor
        # if formula == "Beer A":
        #         if not self.waiting_Over_Gold:
        #             self.waiting_Over_Gold = True
        #         else:
        #             while self.waiting_Over_Gold:
        #                 logger.debug(f"waiting other arm get Beer A")
        #                 time.sleep(1.5)
        #             self.waiting_Over_Gold = True
        # else:
        #     if not self.waiting_Rowdy_IPA:
        #         self.waiting_Rowdy_IPA = True
        #     else:
        #         while self.waiting_Rowdy_IPA:
        #             logger.debug(f"waiting other arm get Rowdy IPA")
        #             time.sleep(1.5)
        #         self.waiting_Rowdy_IPA = True
        # #Move to beer dispensor
        # self.goto_point(which, beer_pose, wait=False, speed=TCP_speed)
        # beer_pose.z = 90
        # # if which == Arm.left:
        # #     self.goto_gripper_position(which, 550, wait=True)
        # # else:
        # # self.goto_gripper_position(which, 400, wait=True)
        # self.goto_temp_point(which, z=beer_pose.z, wait=True, speed=TCP_speed)
        # self.goto_gripper_position(which, 850, wait=True)
        # self.goto_temp_point(which, z=beer_pose.z + 125, wait=False, speed=TCP_speed)
        # if which == Arm.right:
        #     self.goto_temp_point(which, x=beer_pose.x + 100, y=beer_pose.y + 100, wait=False, speed=TCP_speed)
        # else:
        #     self.goto_temp_point(which, x=beer_pose.x + 100, y=beer_pose.y - 100, wait=False, speed=TCP_speed)
        # # self.goto_gripper_position(which, 1, wait=True)
        # #Pushes the cup down onto the dispensor
        # if which == Arm.left:
        #     self.goto_temp_point(which, z=beer_pose.z + 70, wait=False, speed=TCP_speed)
        # else:
        #     self.goto_temp_point(which, z=beer_pose.z + 70, wait=False, speed=TCP_speed)
        # self.goto_temp_point(which, x=beer_pose.x, y=beer_pose.y, z=beer_pose.z + 125, wait=False, speed=TCP_speed)
        # # self.goto_gripper_position(which, 850, wait=True)
        # self.goto_temp_point(which, z=beer_pose.z, wait=True, speed=TCP_speed)
        # # if which == Arm.left:
        # #     self.goto_gripper_position(which, 550, wait=True)
        # # else:
        # self.goto_gripper_position(which, 450, wait=True)
        # #Picks the cup back up
        # time.sleep(2)
        # self.goto_temp_point(which, z=beer_pose.z + 125, wait=False, speed=TCP_speed)
        # #Puts cup down
        # self.goto_point(which, put_cup_pose, wait=False, speed = 275)
        # if formula == "Beer A":
        #     self.waiting_Over_Gold = False
        # else:
        #     self.waiting_Rowdy_IPA = False
        # self.goto_temp_point(which, z=put_cup_pose.z - 128, wait=False, speed=TCP_speed)
        # self.goto_gripper_position(which, 850, wait=True)
        # self.goto_temp_point(which, x=put_cup_pose.x - 122, z=put_cup_pose.z - 128, wait=False, speed=TCP_speed)
        # self.goto_initial_position_direction(which, 0, wait=True, speed=TCP_speed) 

    def make_red_wine(self, formula, sweetness, milk, ice, receipt_number):
        start_time = int(time.time())
        AudioInterface.gtts("Got it, I'm making your drink now!")
        logger.debug('start in make_red_wine')
        # composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk)
        # logger.info(f"into make_red_wine  :{composition}")

        self.right_record.clear()
        try:
            self.right_record.proceed()  # 记录关节位置线程开启
            self.take_cold_cup()
            self.put_cold_cup()
            self.right_record.pause()
        except StopError as stop_err:
            raise stop_err
        except Exception as e:
            self.stop(e)
        finally:
            get_make_time = int(time.time()) - start_time
            logger.info(f"{formula} making use time is : {get_make_time}")

    def make_white_wine(self, formula, sweetness, milk, ice, receipt_number):
        start_time = int(time.time())
        AudioInterface.gtts("Got it, I'm making your drink now!")
        logger.debug('start in make_white_wine')
        # composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk)
        # logger.info(f"into make_white_wine  :{composition}")

        self.left_record.clear()

        try:
            self.left_record.proceed()  # 记录关节位置线程开启
            self.take_hot_cup()
            self.put_hot_cup()
            self.left_record.pause()
        except StopError as stop_err:
            raise stop_err
        except Exception as e:
            self.stop(e)
        finally:
            get_make_time = int(time.time()) - start_time
            logger.info(f"{formula} making use time is : {get_make_time}")

    # All of the IPO event functions
    def make_cold_drink(self, formula, sweetness, milk, ice, receipt_number):
        if formula == "Paper plane with sugar rim":
            logger.error('formula is {}'.format(formula))
            self.make_paper_plane()
        elif formula == "Cosmopolitan":
            logger.error('formula is {}'.format(formula))
            self.make_cosmo()
        elif formula == "Cranberry whiskey sour with sugar rim":
            logger.error('formula is {}'.format(formula))
            self.make_wiskey_sour()
        elif formula == "Vodka screwdriver":
            logger.error('formula is {}'.format(formula))
            self.make_screwdriver()
        elif formula == "Orange juice":
            logger.error('formula is {}'.format(formula))
            self.make_orange_juice()
        elif formula == "Cranberry juice":
            logger.error('formula is {}'.format(formula))
            self.make_cranberry_juice()
        elif formula == "Beer A":
            logger.error('formula is {}'.format(formula))
            self.make_beer(which=Arm.left)
        elif formula == "Beer B":
            logger.error('formula is {}'.format(formula))
            self.make_beer(which=Arm.right)
        elif formula == "Double Beer":
            self.make_double_beer(sweetness=1)
        elif formula == "Double Beer A":
            self.make_rotating_beers(formula)
        elif formula == "Double Beer B":
            self.make_rotating_beers(formula)

    def make_orange_juice(self):
        ###
        # self.take_5oz_cup()
        self.right_hand_take_treacle_and_put(formula='orange juice')

    def make_cranberry_juice(self):
        self.take_5oz_cup()
        self.right_hand_take_treacle_and_put(formula='cranberry juice')

    def make_paper_plane(self):
        def left_action():
            self.take_shaker_and_ice()
            self.take_treacle(pump_num=self.pump_1, pump_time=1)
            self.return_treacle()
            self.take_bottle_pour()

        def right_action():
            self.take_aperol()

        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        self.pour_aperol()
        self.put_aperol()
        self.take_amero()
        self.pour_amaro()
        self.put_amero()
        self.take_cointreau()
        self.pour_cointreau()
        self.put_cointreau()

        def left_action_2():
            self.shake()

        def right_action_2():
            self.take_5oz_cup()
            self.dip_cup()

        thread_list_2 = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
        for t in thread_list_2:
            t.start()
        for t in thread_list_2:
            t.join()

        self.pour_shaker()

        def left_action_3():
            self.wash_shaker()

        def right_action_3():
            self.put_cup()

        thread_list_3 = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
        for t in thread_list_3:
            t.start()
        for t in thread_list_3:
            t.join()

    def make_cosmo(self):
        def left_action():
            self.take_shaker_and_ice()
            self.take_treacle(pump_num=self.pump_2, pump_time=1)
            self.send_pump_command(pump_char=self.pump_3, pump_time=1)
            self.send_pump_command(pump_char=self.pump_5, pump_time=1)
            self.return_treacle()
            self.take_bottle_pour()

        def right_action():
            self.goto_gripper_position(Arm.right, 850, wait=True)

            self.take_cointreau()

        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        self.pour_cointreau_cosmo()

        def left_action_2():
            self.shake()

        def right_action_2():
            self.put_cointreau()

            self.take_5oz_cup()
            self.dip_cup()

        thread_list_2 = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
        for t in thread_list_2:
            t.start()
        for t in thread_list_2:
            t.join()

        self.pour_shaker()

        def left_action_3():
            self.wash_shaker()

        def right_action_3():
            self.put_cup()

        thread_list_3 = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
        for t in thread_list_3:
            t.start()
        for t in thread_list_3:
            t.join()

    def make_wiskey_sour(self):
        def left_action():
            self.take_shaker_and_ice()
            self.take_treacle(pump_num=self.pump_2, pump_time=1)
            self.send_pump_command(pump_char=self.pump_3, pump_time=1)
            self.send_pump_command(pump_char=self.pump_4, pump_time=1)
            self.return_treacle()
            # self.take_bottle_pour()
            self.shake()

        def right_action():
            self.take_5oz_cup()
            self.flip_cup()

        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        self.pour_shaker()

        def left_action_3():
            self.wash_shaker()

        def right_action_3():
            self.put_cup()

        thread_list_3 = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
        for t in thread_list_3:
            t.start()
        for t in thread_list_3:
            t.join()

    def make_screwdriver(self):
        def left_action():
            self.take_shaker_and_ice()
            self.take_treacle(pump_num=self.pump_1, pump_time=1)
            self.send_pump_command(pump_char=self.pump_5, pump_time=1)
            self.return_treacle()
            # self.take_bottle_pour()
            self.shake()

        def right_action():
            self.take_5oz_cup()
            self.flip_cup()

        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        self.pour_shaker()

        def left_action_3():
            self.wash_shaker()

        def right_action_3():
            self.put_cup()

        thread_list_3 = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
        for t in thread_list_3:
            t.start()
        for t in thread_list_3:
            t.join()

    def send_pump_command(self, pump_char="k", pump_time=0):
        port_name = '/dev/ttyS5'
        baudrate = 9600
        pump_num = pump_char
        ser = serial.Serial(port_name, baudrate=baudrate, timeout=1)

        try:
            if ser.isOpen():
                print(f"Connected to {ser.name}")
                command = f"{pump_num}\r\n"

                ser.write(command.encode())

                time.sleep(pump_time)

                command = f"{pump_num.lower()}\r\n"

                ser.write(command.encode())

        except serial.SerialException as e:
            print(f"Error: {e}")

        finally:
            ser.close()

    def send_pump_command_and_wash(self):
        port_name = '/dev/ttyS5'
        baudrate = 9600
        pump_num = self.washer_valve
        ser = serial.Serial(port_name, baudrate=baudrate, timeout=1)

        try:
            if ser.isOpen():
                print(f"Connected to {ser.name}")
                command = f"{pump_num}\r\n"

                ser.write(command.encode())
                speed = 200
                # motion starts here
                for i in range(2):
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([625.5, 24, 118.8, 96.4, -83.8, 48.5]), wait=True, speed=speed)
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 29, 118.8, 96.4, -83.8, 48.5]), wait=True, speed=speed)
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 2.1, 118.8, 96.4, -83.8, 48.5]), wait=True, speed=speed)

                command = f"{pump_num.lower()}\r\n"

                ser.write(command.encode())

        except serial.SerialException as e:
            print(f"Error: {e}")

        finally:
            ser.close()

    def take_shaker_and_ice(self, speed=400):
        self.goto_gripper_position(Arm.left, 850, wait=False)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.8, 398.9, 293.8, -130.5, 87.4, -131.7]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.8, 398.9, 112.9, -130.5, 87.4, -131.7]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.left, 50, wait=True)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([440.5, 990.6, 309.5, -100.6, 83.9, -7.6]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([339.4, 1002.1, 302.7, -97.7, 79.3, -4.7]), wait=True, speed=speed)
        time.sleep(3)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([440.5, 990.6, 309.5, -100.6, 83.9, -7.6]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)

    def take_treacle(self, speed=500, pump_num="k", pump_time=0):
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([563.8, 54.8, 155.0, 155.7, 88.0, 115.3]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([703.8, 4.3, 155.0, 155.7, 88.0, 115.3]), wait=True, speed=speed)

        self.send_pump_command(pump_num, pump_time)

    def return_treacle(self, speed=500):

        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([563.8, 54.8, 155.0, 155.7, 88.0, 115.3]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([487.5, 250.6, 287.7, -103.0, 85.0, -157.5]), wait=True, speed=speed)

    def shake(self, speed=400):
        i = 0
        while (i < 10):
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([487.5, 300.0, 287.7, -94.3, 75.0, -148.7]), wait=False, speed=speed)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([487.5, 180.0, 287.7, 96.1, 79.3, 41.5]), wait=False, speed=speed)
            self.goto_point(Arm.left, common_schema.Pose.list_to_obj([380.0, 240.0, 287.7, 101.5, 84.4, 46.8]), wait=False, speed=speed)
            i += 1

    def pour_shaker(self, speed=200):
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([646.6, 93.2, 341.6, -158.0, 85.1, 150.7]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([657.4, 93.7, 375.0, 97.1, 66.6, 45.1]), wait=False, speed=speed)
        speed = 150
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([676.0, 92.5, 452.7, 88.3, 12.4, 38.2]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([659.6, 70.7, 497.5, 85.9, -10.8, 36.4]), wait=True, speed=speed)
        time.sleep(2)
        speed = 300
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([676.0, 92.5, 452.7, 88.3, 12.4, 38.2]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([657.4, 93.7, 375.0, 97.1, 66.6, 45.1]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([646.6, 93.2, 341.6, -158.0, 85.1, 150.7]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.9, 401.9, 284.6, -156.4, 85.0, -157.5]), wait=False, speed=speed)

    def wash_shaker(self, speed=400):
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([646.4, 14.1, 155.0, 177.2, 88.2, 136.8]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([562.8, -62.3, 131.3, -99.2, -29.1, -136.9]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([651.1, 24.3, 124.6, 96.4, -83.8, 48.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 25.6, 118.8, 96.4, -83.8, 48.5]), wait=True, speed=speed)
        self.send_pump_command_and_wash()
        speed = 300
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 25.6, 118.8, 96.4, -83.8, 48.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 25.6, 170.0, 96.4, -83.8, 48.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([649.2, 25.6, 170.0, -90.9, -43.1, -124.5]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.8, 398.9, 170.0, -130.5, 87.4, -131.7]), wait=False, speed=speed)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.8, 398.9, 112.9, -130.5, 87.4, -131.7]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.left, 850, wait=True)
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.8, 398.9, 350.0, -130.5, 87.4, -131.7]), wait=True, speed=speed)

    def take_5oz_cup(self, speed=500):
        self.reset_right_tcp_load()
        self.goto_gripper_position(Arm.right, 850, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([375.0, -512.3, 179.6, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([-10.7, -855.1, 136.3, 96.6, 87.5, 8.2]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([4.4, -865.7, 58.1, -178.3, 89.3, 93.5]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.right, 50, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([1.7, -859.6, 138.5, 125.3, 88.8, 37.1]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([375.0, -512.3, 179.6, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        time.sleep(3)

    def flip_cup(self, speed=300):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 110.4, 42.4, -88.3, 137.5]), wait=True, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([557.9, 13.9, 383.2, 14.6, -88.1, -132.6]), wait=True, speed=speed)

    def right_hand_take_treacle_and_put(self, formula, speed=500):
        self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-199.5, -2.9, -52.8, 95.3, 82.4, -215.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([713.2, 20.5, 238.0, 28.3, -88.6, -168.5]), wait=True, speed=speed)
        ### Testing, comment back in later
        # if formula == 'orange juice':
        #     self.send_pump_command(pump_char='A', pump_time=2)
        # else:
        #     self.send_pump_command(pump_char='B', pump_time=2)
        speed = 350
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([679.2, -262.9, 137.9, 28.3, -88.6, 175.6]), wait=True, speed=speed)
        speed = 500
        self.goto_gripper_position(Arm.right, 600, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([514.3, -336.0, 143.1, 28.3, -88.6, 175.6]), wait=False, speed=speed)
        self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-199.5, -2.9, -52.8, 95.3, 82.4, -215.3]), wait=False, speed=speed)

    def dip_cup(self, speed=200):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([375.0, -512.3, 179.6, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([502.3, -348.4, 110.4, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([502.3, -348.4, 79.5, -61.2, 87.4, -61.3]), wait=True, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([502.3, -348.4, 110.4, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 110.4, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 78.5, -61.2, 87.4, -61.3]), wait=True, speed=speed)
        speed = 100
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([486.7, -223.0, 78.8, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.5, -215.5, 78.8, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.5, -229.0, 78.8, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        speed = 300
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 110.4, -61.2, 87.4, -61.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 110.4, 42.4, -88.3, 137.5]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([557.9, 13.9, 383.2, 14.6, -88.1, -132.6]), wait=False, speed=speed)

    def put_cup(self, speed=500):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 194.2, 73.1, -88.3, 137.5]), wait=True, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([688.2, -269.3, 181.6, 73.1, -88.3, 127.5]), wait=True, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([688.2, -269.3, 137.3, 73.1, -88.3, 127.5]), wait=True, speed=speed)
        self.goto_gripper_position(Arm.right, 850, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([688.2, -269.3, 206.7, 73.1, -88.3, 127.5]), wait=True, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -223.0, 194.2, 73.1, -88.3, 137.5]), wait=True, speed=speed)

    def take_aperol(self, speed=500):
        # set tcp load to 2.5
        weight = self.adam_config.gripper_config['pour_vermouth'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_vermouth'].tcp_load.center_of_gravity.dict().values())
        self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)

        self.goto_gripper_position(Arm.right, 850, wait=False)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([579.1, -709.9, 158.6, 108.6, 88.7, 88.2]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([681.7, -748.2, 142.6, -118.4, 89.1, -138.8]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([681.7, -748.2, 210.4, -118.4, 89.1, -138.8]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([483.0, -636.1, 211.6, -141.3, 89.1, -138.8]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    def reset_right_tcp_load(self):
        default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
        default_tool_gravity = list(
            self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
        self.left.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)  # 恢复默认设置夹爪载重

    def put_aperol(self, speed=500):

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=speed)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([483.0, -636.1, 211.6, -141.3, 89.1, -138.8]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([681.7, -748.2, 210.4, -118.4, 89.1, -138.8]), wait=True, speed=speed)
        speed = 300
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([681.7, -748.2, 142.6, -118.4, 89.1, -138.8]), wait=True, speed=speed)
        self.goto_gripper_position(Arm.right, 850, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([579.1, -709.9, 158.6, 108.6, 88.7, 88.2]), wait=False, speed=speed)

    def take_amero(self, speed=500):
        self.goto_gripper_position(Arm.right, 850, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([557.0, -596.9, 126.3, 53.1, 89.3, 55.9]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([667.5, -591.4, 127.1, 53.1, 89.3, 55.9]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([667.5, -591.4, 266.8, 53.1, 89.3, 55.9]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([471.5, -562.0, 265.8, 33.3, 89.3, 55.9]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    def put_amero(self, speed=500):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=speed)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([471.5, -562.0, 265.8, 33.3, 89.3, 55.9]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([667.5, -591.4, 266.8, 53.1, 89.3, 55.9]), wait=False, speed=speed)
        speed = 400
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([667.5, -591.4, 127.1, 53.1, 89.3, 55.9]), wait=True, speed=speed)
        self.goto_gripper_position(Arm.right, 850, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([520.0, -596.9, 126.3, 53.1, 89.3, 55.9]), wait=False, speed=speed)

    def take_cointreau(self, speed=500):
        # set tcp load to 2.5
        weight = self.adam_config.gripper_config['pour_vermouth'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_vermouth'].tcp_load.center_of_gravity.dict().values())
        self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([661.2, -433.2, 329.8, 118.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.5, -433.2, 114.8, 118.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.5, -433.2, 264.2, 118.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([477.2, -336.2, 267.2, 108.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    def put_cointreau(self, speed=500):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=speed)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([477.2, -336.2, 267.2, 108.9, 89.2, 155.7]), wait=False, speed=speed)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.5, -433.2, 264.2, 118.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([672.5, -433.2, 114.8, 118.9, 89.2, 155.7]), wait=False, speed=speed)
        self.goto_gripper_position(Arm.right, 850, wait=True)

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([661.2, -433.2, 329.8, 118.9, 89.2, 155.7]), wait=True, speed=speed)

    def pour_aperol(self, speed=200):

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=231)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([637.9, -170.1, 425.0, -91.0, 30.1, -60.4]), wait=False, speed=231)
        # self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([617.8, -173.9, 510.5, -85.9, -1.2, -65.2]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([584.7, -153.3, 595.3, -77.5, -31.0, -66.6]), wait=False, speed=speed)
        time.sleep(0.5)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([600.1, -192.7, 475.6, -92.9, 2.3, -65.3]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=speed)

    def take_bottle_pour(self):
        # recive bottle pour pos
        self.goto_point(Arm.left, common_schema.Pose.list_to_obj([506, 40, 359.6, -70.5, 85.0, -157.5]), wait=True, speed=300)
        # _______-----___---_-__-___-------_----__------------------------_________________------

    def pour_amaro(self, speed=200):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=231)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([611.8, -130.5, 468.1, -91.0, 30.1, -60.4]), wait=False, speed=231)
        # self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([611.8, -108.1, 507.2, -90.9, 2.6, -59.9]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([590.4, -87.3, 575.2, -81.2, -35.0, -62.2]), wait=True, speed=speed)
        time.sleep(1)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([606.5, -124.0, 508.7, -92.9, -8.2, -59.8]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    def pour_cointreau(self, speed=100):
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=231)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([615.3, -144.4, 405.5, -91.0, 30.1, -60.4]), wait=False, speed=231)
        # self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -135.4, 498.2, -85.9, -1.2, -65.2]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([587.3, -137.9, 557.6, -85.6, -20.8, -66.7]), wait=True, speed=speed)
        time.sleep(1.15)
        speed = 400
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    def pour_cointreau_cosmo(self, speed=100):

        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=False, speed=231)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([615.3, -144.4, 405.5, -91.0, 30.1, -60.4]), wait=False, speed=231)
        # self.goto_gripper_position(Arm.right, 100, wait=True)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -135.4, 498.2, -85.9, -1.2, -65.2]), wait=False, speed=speed)
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([587.3, -137.9, 557.6, -85.6, -20.8, -66.7]), wait=True, speed=speed)
        time.sleep(0.01)
        speed = 400
        self.goto_point(Arm.right, common_schema.Pose.list_to_obj([598.9, -192.7, 425.7, -168.9, 89.1, -138.8]), wait=True, speed=speed)

    # All of the F1 Functions

    # def take_cup_martini(self, speed = 400):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([264.9, -448.9, 285.1, 91.4, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([87.6, -690.2, 128.7, -178.5, 88.2, 92.0]), wait=False, speed = speed)
    #     self.goto_gripper_position(Arm.right, 350, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([231.3, -689.1, 128.8, 179.5, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([235.0, -1132.1, 114.9, 179.5, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([235.1, -1141.3, 408.0, 179.5, 88.2, 90.0]), wait=False, speed = speed)

    # def take_mix(self, speed =600):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([171.0, -698.0, 432.4, 120.8, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([255.2, -380.0, 374.5, 65.2, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -35.5, 430.3, 40.3, 88.2, 90.0]), wait=True, speed = speed)

    # def take_vodka(self, speed = 400):
    #     self.goto_gripper_position(Arm.right, 850, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([211.8, -572.9, 148.8, 105.3, 89.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300.3, -597.0, 150.5, 105.3, 89.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([378.9, -627.0, 148.3, 37.0, 87.8, 21.7]), wait=True, speed = speed)
    #     self.goto_gripper_position(Arm.right, 100, wait=True)
    #     weight = self.adam_config.gripper_config['pour_vermouth'].tcp_load.weight
    #     tool_gravity = list(self.adam_config.gripper_config['pour_vermouth'].tcp_load.center_of_gravity.dict().values())
    #     self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([369.7, -620.2, 229.0, 11.5, 83.4, -3.8]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([253.7, -409.6, 213.4, -18.0, 84.8, 19.5]), wait=True, speed = speed)

    # def take_vermouth(self, speed = 500):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([345.9, -415.6, 341.3, 12.0, 87.1, 8.4]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([387.9, -452.5, 152.5, 18.7, 87.1, 7.9]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([523.4, -478.6, 159.1, 18.8, 87.1, 7.9]), wait=True, speed = speed)
    #     self.goto_gripper_position(Arm.right, 170, wait=True)
    #     weight = self.adam_config.gripper_config['pour_vermouth'].tcp_load.weight
    #     tool_gravity = list(self.adam_config.gripper_config['pour_vermouth'].tcp_load.center_of_gravity.dict().values())
    #     self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([517.1, -479.5, 283.9, 18.7, 87.1, 7.8]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([359.3, -414.9, 276.3, 11.8, 87.1, 7.8]), wait=True, speed = speed)

    # def take_hendricks(self, speed = 500):
    #     self.goto_gripper_position(Arm.right, 850, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([345.9, -415.6, 341.3, 12.0, 87.1, 8.4]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([496.3, -314.2, 233.7, 6.0, 87.2, 8.1]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([503.1, -313.3, 95.3, 6.0, 87.2, 8.1]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([573.2, -310.7, 98.7, 6.0, 87.2, 8.1]), wait=True, speed = speed)
    #     self.goto_gripper_position(Arm.right, 350, wait=True)
    #     weight = self.adam_config.gripper_config['pour_hendricks'].tcp_load.weight
    #     tool_gravity = list(self.adam_config.gripper_config['pour_hendricks'].tcp_load.center_of_gravity.dict().values())
    #     self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([565.5, -311.8, 257.5, 6.0, 87.2, 8.1]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([489.1, -157.7, 350.7, -8.1, 87.1, 12.1]), wait=True, speed = speed)

    # def clean_f1_shaker(self, speed = 500):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([386.3, 548.0, 139.6, -36.8, 87.1, -36.5]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([510.0, 564.2, 135.4, 68.3, 87.0, 70.4]), wait=True, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([510.5, 555.5, 127.0, 66.8, -87.2, 115.3]), wait=True, speed = 800)
    #     # self.arduino.arduino.send_one_msg('b')
    #     time.sleep(3)
    #     # self.arduino.arduino.send_one_msg('b')
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([510.0, 564.2, 135.4, 68.3, 87.0, 70.4]), wait=True, speed = 800)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([386.3, 548.0, 139.6, -36.8, 87.1, -36.5]), wait=False, speed = speed)

    # def shaker_pour_old(self, speed = 400):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([536.2, 234.9, 390.2, 70.6, 87.0, 70.4]), wait=True, speed = speed)

    #     # checks if the martini cup is at the right position
    #     while True:
    #         current_position = self.current_position(Arm.right)
    #         cur_pos = str(current_position)
    #         list1 = cur_pos.split(" ")
    #         list2 = list1[1].split("=")
    #         right_y = float(list2[1])
    #         if right_y  == -35.5:
    #             #pour starts
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([590.3, 84.3, 500.6, 88.9, 11.5, 64.9]), wait=True, speed = 200)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([603.3, 50.4, 536.5, 85.2, -21.5, 65.5]), wait=True, speed = 100)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([584.0, 3.9, 561.7, 80.8, -54.0, 57.4]), wait=True, speed = 100)
    #             time.sleep(3)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([603.3, 50.4, 536.5, 85.2, -21.5, 65.4]), wait=True, speed = 100)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([590.3, 84.3, 500.6, 88.9, 11.5, 64.9]), wait=True, speed = 400)
    #             # pour ends
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([606.4, 134.0, 472.7, 124.6, 87.5, 104.0]), wait=True, speed = 400)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([630.3, 234.4, 391.8, 70.6, 87.0, 70.4]), wait=True, speed = 400)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([528.1, 224.0, 235.7, 83.1, 87.0, 70.4]), wait=True, speed = 400)
    #             break
    #         else:
    #             time.sleep(0.1)

    # def shaker_pour(self, speed = 400):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([582.4, 116.9, 335.9, 34.1, 87.8, 16.0]), wait=True, speed = speed)
    #     # checks if the martini cup is at the right position
    #     while True:
    #         current_position = self.current_position(Arm.right)
    #         cur_pos = str(current_position)
    #         list1 = cur_pos.split(" ")
    #         list2 = list1[1].split("=")
    #         right_y = float(list2[1])
    #         if right_y  == -32.3:
    #             #pour starts
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([578.5, 120.1, 380.4, 87.5, 28.6, 74.4]), wait=True, speed = 300)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([572.5, 74.8, 412.6, 88.7, -2.5, 75.6]), wait=True, speed = 100)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([578.4, 49.9, 444.5, 94.6, -26.0, 74.3]), wait=True, speed = 100)
    #             time.sleep(3)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([578.5, 120.1, 380.4, 87.5, 28.6, 74.4]), wait=True, speed = 400)
    #             # pour ends
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([582.4, 116.9, 335.9, 34.1, 87.8, 16.0]), wait=True, speed = 400)
    #             self.goto_point(Arm.left, common_schema.Pose.list_to_obj([630.3, 234.4, 391.8, 70.6, 87.0, 70.4]), wait=True, speed = 400)
    #             # self.goto_point(Arm.left, common_schema.Pose.list_to_obj([528.1, 224.0, 235.7, 83.1, 87.0, 70.4]), wait=True, speed = 400)
    #             break
    #         else:
    #             time.sleep(0.1)

    # def take_mix(self, speed =600):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([171.0, -698.0, 432.4, 120.8, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([255.2, -380.0, 374.5, 65.2, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -32.3, 327.9, 40.3, 88.2, 90.0]), wait=True, speed = speed)

    # def f1_put_shaker(self, speed = 700):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([386.3, 548.0, 139.6, -36.8, 87.1, -36.5]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([549.9, 222.2, 267.1, 172.3, 88.5, 160.4]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([546.5, 222.2, 113.5, -107.1, 88.8, -119.0]), wait=False, speed = speed)
    #     self.goto_gripper_position(Arm.left, 850, wait=True)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([426.5, 283.9, 111.6, -124.9, 87.7, -136.8]), wait=False, speed = speed)
    #     self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=300)

    # def take_treacle(self, speed = 500):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([386.3, 548.0, 139.6, -36.8, 87.1, -36.5]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([498.4, 536.7, 132.1, -160.3, 85.0, -160.1]), wait=True, speed = speed)

    # def out_treacle(self, speed = 500):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([338.3, 548.8, 168.0, -47.0, 87.7, -46.7]), wait=True, speed = speed)

    # def pour_to_shaker(self, speed = 500):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([487.6, 176.7, 255.4, -18.6, 87.9, -58.6]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([479.9, -6.2, 189.8, 24.0, 87.9, -61.1]), wait=True, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([462.4, 30.1, 210.4, 177.9, 69.6, 92.9]), wait=True, speed = speed)

    # def end_pour_to_shaker(self, speed = 500):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([479.9, -6.2, 189.8, 24.0, 87.9, -61.1]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([487.6, 176.7, 255.4, -18.6, 87.9, -58.6]), wait=False, speed = speed)

    # def f1_shake(self, speed = 300):
    #     self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=300)
    #     # going to first point on the shake
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([212.0, 361.8, 364.5, 19.7, 88.4, 10.1]), wait=False, speed = speed)
    #     for x in range(16):
    #         self.goto_point(Arm.left, common_schema.Pose.list_to_obj([212.0, 361.8, 364.5, 87.0, 60.3, 77.8]), wait=False, speed = 450)
    #         self.goto_point(Arm.left, common_schema.Pose.list_to_obj([245.5, 560.2, 366.4, -86.2, 66.6, -96.1]), wait=False, speed = 450)
    #         self.goto_point(Arm.left, common_schema.Pose.list_to_obj([328.2, 459.2, 368.1, 21.0, 88.4, 11.3]), wait=False, speed = 450)
    #         if x == 16:
    #             break     

    # def take_shaker(self, speed = 700):
    #     self.goto_gripper_position(Arm.left, 850, wait=True)
    #     self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=300)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([426.5, 283.9, 111.6, -124.9, 87.7, -136.8]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([546.5, 222.2, 113.5, -107.1, 88.8, -119.0]), wait=False, speed = speed)
    #     self.goto_gripper_position(Arm.left, 300, wait=True)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([547.2, 223.1, 159.2, 172.3, 88.5, 160.4]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([360.4, 445.9, 159.5, -134.4, 87.7, -136.7]), wait=False, speed = speed)

    # def take_ice_maker(self, speed = 700):
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([360.4, 445.9, 159.5, -134.4, 87.7, -136.7]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([392.4, 1000.8, 318.8, -94.6, 59.9, 2.8]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([288.9, 987.8, 300.1, -94.6, 59.9, 2.8]), wait=True, speed = speed)
    #     time.sleep(4)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([393.7, 971.8, 323.6, -114.6, 84.4, -17.8]), wait=True, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([360.4, 700.4, 328.6, -81.4, 84.4, -17.8]), wait=False, speed = speed)
    #     self.goto_point(Arm.left, common_schema.Pose.list_to_obj([360.4, 445.9, 159.5, -134.4, 87.7, -136.7]), wait=False, speed = speed)

    # def put_martini(self, speed = 300):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -35.5, 430.3, 40.3, 88.2, 90.0]), wait=False, speed = 250)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -28.2, 205.0, 40.3, 88.2, 90.0]), wait=False, speed = 150)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -28.2, 198.0, 40.3, 88.2, 90.0]), wait=False, speed = 150)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([547.5, -25.6, 116.6, 40.3, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([311.3, -304.0, 107.9, 40.3, 88.2, 90.0]), wait=False, speed = speed)
    #     self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)

    # def pour_vermouth(self, speed = 400):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([499.5, -229.7, 361.8, 4.5, 87.1, 7.8]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([476.6, -234.5, 345.5, -87.1, -7.1, -87.0]), wait=False, speed = 200)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([472.7, -226.4, 412.4, -86.6, -25.8, -88.2]), wait=True, speed = 150)
    #     time.sleep(1)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([476.6, -234.5, 345.5, -87.1, -7.1, -87.0]), wait=True, speed = 150)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([480.4, -257.9, 305.7, -87.0, 3.2, -86.6]), wait=True, speed = speed)

    # def pour_vodka(self, speed = 400):
    #     while True:
    #         current_position = self.current_position(Arm.left)
    #         cur_pos = str(current_position)
    #         list1 = cur_pos.split(" ")
    #         list2 = list1[1].split("=")
    #         left_y = float(list2[1])
    #         if left_y  == -6.2:
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([469.2, -247.7, 434.9, -11.0, 87.8, -7.8]), wait=False, speed = 300)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([469.5, -256.5, 298.5, -87.8, 2.8, -86.7]), wait=False, speed = speed)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([465.6, -253.6, 398.1, -87.8, -17.1, -87.5]), wait=False, speed = 200)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([462.5, -231.1, 448.8, -87.5, -29.2, -88.0]), wait=True, speed = 150)
    #             time.sleep(3)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([469.5, -256.5, 298.5, -87.8, 2.8, -86.7]), wait=True, speed = 150)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([449.9, -248.8, 434.2, -11.0, 87.8, -7.8]), wait=False, speed = speed)
    #             break
    #         else:
    #             time.sleep(0.1)

    # def pour_hendricks(self, speed = 200):
    #     while True:
    #         current_position = self.current_position(Arm.left)
    #         cur_pos = str(current_position)
    #         list1 = cur_pos.split(" ")
    #         list2 = list1[1].split("=")
    #         left_y = float(list2[1])
    #         if left_y  == -6.2:
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([496.0, -176.7, 325.1, -90.9, 0.4, -80.3]), wait=False, speed = speed)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -170.8, 359.7, -90.8, -13.7, -76.7]), wait=False, speed = speed)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([504.5, -144.6, 430.6, -91.0, -39.4, -76.3]), wait=False, speed = speed)
    #             time.sleep(3)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([509.7, -170.8, 359.7, -90.8, -13.7, -76.7]), wait=False, speed = speed)
    #             self.goto_point(Arm.right, common_schema.Pose.list_to_obj([496.0, -176.7, 325.1, -90.9, 0.4, -80.3]), wait=False, speed = speed)
    #             break
    #         else:
    #             time.sleep(0.1)

    # def put_vodka(self, speed = 400):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([321.1, -606.8, 321.8, 26.4, 87.8, 10.3]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([369.7, -620.2, 229.0, 11.5, 83.4, -3.8]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([378.9, -627.0, 148.3, 37.0, 87.8, 21.7]), wait=True, speed = speed)
    #     time.sleep(1)
    #     self.goto_gripper_position(Arm.right, 850, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([276.8, -590.6, 150.5, 105.3, 89.2, 90.0]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([306.2, -460.2, 363.6, 27.5, 84.5, 28.0]), wait=False, speed = speed)

    # def put_vermouth(self, speed = 400):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([344.5, -422.8, 317.5, 28.0, 87.1, 7.8]), wait=False, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([517.1, -479.5, 283.9, 18.7, 87.1, 7.9]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([523.4, -478.6, 159.1, 18.7, 87.1, 7.8]), wait=True, speed = speed)
    #     self.goto_gripper_position(Arm.right, 850, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([387.9, -452.5, 152.5, 18.7, 87.1, 7.9]), wait=False, speed = speed)

    # def put_hendricks(self, speed = 400):
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([563.8, -311.1, 248.5, 171.0, 86.7, 173.1]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([573.2, -310.7, 98.7, 6.0, 87.2, 8.1]), wait=True, speed = speed)
    #     self.goto_gripper_position(Arm.right, 850, wait=True)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([503.1, -313.3, 95.3, 6.0, 87.2, 8.1]), wait=True, speed = speed)
    #     self.goto_point(Arm.right, common_schema.Pose.list_to_obj([496.3, -314.2, 233.7, 6.0, 87.2, 8.1]), wait=True, speed = speed)

    # def make_vodka_martini(self, formula):
    #     def left_action():
    #         self.take_shaker()

    #     def right_action():
    #         self.take_vodka()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_ice_maker()

    #     # treacle premixes
    #     if formula in ['Dirty Vodka Martini']:
    #         self.take_treacle()
    #         self.arduino.arduino.send_one_msg('m')
    #         time.sleep(1)
    #         self.arduino.arduino.send_one_msg('m')

    #     # adding alcohol to shaker

    #     def left_action_2():
    #         self.pour_to_shaker()

    #     def right_action_2():
    #         self.pour_vodka()

    #     thread_list = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_vodka()
    #     self.take_vermouth()
    #     self.pour_vermouth()
    #     self.end_pour_to_shaker()

    #     def left_action_3():
    #         self.f1_shake()

    #     def right_action_3():
    #         self.put_vermouth()

    #     thread_list = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
    #     for t in thread_list:
    #         t.start()
    #         t.join()

    #     self.rotate_take_cup()
    #     #self.take_mix()
    #     self.shaker_pour()

    #     def left_action():
    #         self.clean_f1_shaker()

    #     def right_action():
    #         self.put_martini()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.f1_put_shaker()

    # def vodka_martini_demo_2(self):
    #     def left_action():
    #         self.take_shaker()

    #     def right_action():
    #         self.take_vodka()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_ice_maker()

    #     # treacle premixes
    #     # self.take_treacle()
    #     # self.arduino.arduino.send_one_msg('m')
    #     # time.sleep(1)
    #     # self.arduino.arduino.send_one_msg('m')

    #     # adding alcohol to shaker

    #     def left_action_2():
    #         self.pour_to_shaker()

    #     def right_action_2():
    #         self.pour_vodka()

    #     thread_list = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_vodka()
    #     self.take_vermouth()
    #     self.pour_vermouth()
    #     self.end_pour_to_shaker()

    #     def left_action_3():
    #         self.f1_shake()

    #     def right_action_3():
    #         self.put_vermouth()

    #     thread_list = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_cup_martini()
    #     self.take_mix()
    #     self.shaker_pour()

    #     def left_action():
    #         self.clean_f1_shaker()

    #     def right_action():
    #         self.put_martini()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.f1_put_shaker()

    # def make_gin_martini(self,formula):
    #     def left_action():
    #         self.take_shaker()

    #     def right_action():
    #         self.take_hendricks()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_ice_maker()

    #     # treacle premixes
    #     if formula in ['Dirty Gin Martini']:
    #         self.take_treacle()
    #         self.arduino.arduino.send_one_msg('m')
    #         time.sleep(1)
    #         self.arduino.arduino.send_one_msg('m')

    #     # adding alcohol to shaker

    #     def left_action_2():
    #         self.pour_to_shaker()

    #     def right_action_2():
    #         self.pour_hendricks()

    #     thread_list = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_hendricks()
    #     self.take_vermouth()
    #     self.pour_vermouth()
    #     self.end_pour_to_shaker()

    #     def left_action_3():
    #         self.f1_shake()

    #     def right_action_3():
    #         self.put_vermouth()

    #     thread_list = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.rotate_take_cup()
    #     self.shaker_pour()

    #     def left_action():
    #         self.clean_f1_shaker()

    #     def right_action():
    #         self.put_martini()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.f1_put_shaker()

    # def gin_martini_demo_2(self):
    #     def left_action():
    #         self.take_shaker()

    #     def right_action():
    #         self.take_hendricks()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_ice_maker()

    #     # treacle premixes
    #     # self.take_treacle()
    #     # self.arduino.arduino.send_one_msg('m')
    #     # time.sleep(1)
    #     # self.arduino.arduino.send_one_msg('m')

    #     # adding alcohol to shaker
    #     def left_action_2():
    #         self.pour_to_shaker()

    #     def right_action_2():
    #         self.pour_hendricks()

    #     thread_list = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_hendricks()
    #     self.take_vermouth()
    #     self.pour_vermouth()
    #     self.end_pour_to_shaker()

    #     def left_action_3():
    #         self.f1_shake()

    #     def right_action_3():
    #         self.put_vermouth()

    #     thread_list = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_cup_martini()
    #     self.take_mix()
    #     self.shaker_pour()

    #     def left_action():
    #         self.clean_f1_shaker()

    #     def right_action():
    #         self.put_martini()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.f1_put_shaker()

    # def make_cosmo_espresso(self,formula):

    #     AudioInterface.music('f1_cosmo.mp3')

    #     def left_action():
    #         self.take_shaker()

    #     def right_action():
    #         self.take_vodka()

    #     thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.take_ice_maker()

    #     # treacle premixes
    #     if formula in ['Cosmopolitan']:
    #         self.take_treacle()
    #         self.arduino.arduino.send_one_msg('m')
    #         time.sleep(1)
    #         self.arduino.arduino.send_one_msg('m')
    #     elif formula in ['Espresso Martini']:
    #         self.take_treacle()
    #         self.arduino.arduino.send_one_msg('o')
    #         time.sleep(1)
    #         self.arduino.arduino.send_one_msg('o')

    #     # adding alcohol to shaker

    #     def left_action_2():
    #         self.pour_to_shaker()

    #     def right_action_2():
    #         self.pour_vodka()

    #     thread_list = [threading.Thread(target=right_action_2), threading.Thread(target=left_action_2)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_vodka()
    #     self.end_pour_to_shaker()

    #     def left_action_3():
    #         self.f1_shake()
    #         self.shaker_pour()

    #     def right_action_3():
    #         self.rotate_take_cup()

    #     thread_list = [threading.Thread(target=right_action_3), threading.Thread(target=left_action_3)]
    #     for t in thread_list:
    #         t.start()
    #     for t in thread_list:
    #         t.join()

    #     self.put_martini()
    #     self.clean_f1_shaker()
    #     self.f1_put_shaker()

    # def f1_make_drink(self, formula):
    #     if formula in ['Dirty Vodka Martini','Vodka Martini']:
    #         self.make_vodka_martini(formula)
    #     elif formula in ['Dirty Gin Martini','Gin Martini']:
    #         self.make_gin_martini(formula)
    #     elif formula in ['Espresso Martini','Cosmopolitan']:
    #         self.make_cosmo_espresso(formula)    

    def take_ingredients_cold_brew(self):
        self.cup_counts
        """
        接糖浆等配料，左手拿杯子就左手去接，右手拿杯子就右手去接
        """
        pose_speed = 300  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        take_pose = deepcopy(tap_pose)
        take_pose.z = 155  # 龙头下方位置
        open_dict = {}  # {'tap_0': 150} arduino打开水泵需要字段
        first_run_flag = True
        self.thread_lock.acquire()
        if first_run_flag:
            self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 运动到龙头下方位置
            self.goto_temp_point(which, x=take_pose.x + 20, speed=pose_speed, wait=True)  # 向上运动，准备接各种配料
            char = "d"
            if not ser.isOpen():
                ser.open()
                time.sleep(1)
            ser.write(char.encode('utf-8'))
            logger.info('sent {}'.format(char))
            time.sleep(15)
            ser.write(char.encode('utf-8'))

            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            first_run_flag = False
            # machine_config = CoffeeInterface.get_machine_config(name)
            # machine_name = '{}_{}'.format(machine_config.get('machine'), machine_config.get('num'))
            # open_dict[machine_name] = quantity
            # logger.info('prepare open {} for {} ml'.format(machine_name, quantity))
            # logger.debug('arduino open_dict = {}'.format(open_dict))
            # CoffeeInterface.post_use(name, quantity)
        # self.arduino.open_port(open_dict) # todo 控制arduino打开接奶，以实际测试为准
        time.sleep(2)  # 模拟等待接配料时间
        if not first_run_flag:  # 机械臂有动作
            # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 运动回零点
            pass
        self.thread_lock.release()

    def take_ingredients_demo(self):
        """
        接糖浆等配料，左手拿杯子就左手去接，右手拿杯子就右手去接
        """
        pose_speed = 400  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        self.goto_initial_position_direction(which, tap_pose.roll, wait=True, speed=pose_speed)
        take_pose = deepcopy(tap_pose)
        take_pose.z = 110  # 龙头下方位置
        open_dict = {}  # {'tap_0': 150} arduino打开水泵需要字段
        first_run_flag = True
        self.thread_lock.acquire()
        if first_run_flag:
            self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
            self.goto_temp_point(which, x=take_pose.x + 20, speed=pose_speed, wait=True)  # 向上运动，准备接各种配料
            char = "c"
            if not ser.isOpen():
                ser.open()
                time.sleep(1)
            ser.write(char.encode('utf-8'))
            logger.info('sent {}'.format(char))
            time.sleep(5)
            ser.write(char.encode('utf-8'))

            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            first_run_flag = False
            # machine_config = CoffeeInterface.get_machine_config(name)
            # machine_name = '{}_{}'.format(machine_config.get('machine'), machine_config.get('num'))
            # open_dict[machine_name] = quantity
            # logger.info('prepare open {} for {} ml'.format(machine_name, quantity))
            # logger.debug('arduino open_dict = {}'.format(open_dict))
            # CoffeeInterface.post_use(name, quantity)
        # self.arduino.open_port(open_dict) # todo 控制arduino打开接奶，以实际测试为准
        time.sleep(2)  # 模拟等待接配料时间
        if not first_run_flag:  # 机械臂有动作
            # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 运动回零点
            pass
        self.thread_lock.release()

    def make_matcha_latte(self):
        self.take_hot_cup()
        self.take_ingredients_left_demo()  # matcha

        def right_action():
            self.take_foam_cup()
            self.make_foam_demo()

        def left_action():
            self.take_coffee_machine_demo_make()  # espresso
            self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)

        # self.take_coffee_machine_demo()#hot milk
        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        self.pour("ice")
        # self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=500)
        self.put_hot_cup()
        self.clean_foamer()
        self.put_foam_cup()

    def take_ice_machine(self):
        speed = 200
        which = Arm.left
        self.goto_point(which, *[-408.3, 15.6, 268.2, 90.3, -1.0, -153.0], wait=True, speed=speed)  # 运动到过渡位置

    def take_coffee_machine_demo_make(self):
        """
        "coffee": {
            "count": 60,
            "coffee_make": {"drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
                        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
                        "coffeeMilkTogether": 0, "adjustOrder": 1}
            }
        """
        pose_speed = 200  # 800
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.left
        # 咖啡机出口高度 - （杯子高度 - 夹爪抓杯高度）-3cm
        coffee_pose.z = coffee_pose.z - (cup_config.high - cup_config.pose.z) - 30
        coffee_pose.roll = self.get_xy_initial_angle(which, coffee_pose.x, coffee_pose.y)

        self.goto_initial_position_direction(which, coffee_pose.roll, wait=False, speed=pose_speed)  # 运动回零点，朝向咖啡机方向
        self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
        try:
            if self.coffee_driver.query_status().get('system_status') != CoffeeMachineStatus.idle:
                # 制作前检查咖啡机状态,必须为idle
                raise CoffeeError('Sorry coffee machine is not prepared, status is {}'.format(
                    self.coffee_driver.query_status()))
            # logger.debug('coffee_make = {}'.format(composition.get('coffee').get('coffee_make')))
            self.coffee_driver.make_coffee('latte', 380)
            while status_msg := self.coffee_driver.query_status():
                status = status_msg.get('system_status')
                error_msg = status_msg.get('error_msg', [])
                # 制作过程中，如果不是making状态就退出循环，否则一直等待
                if status != CoffeeMachineStatus.making:
                    break
                # 制作过程中有报错信息，立刻抛出异常
                if error_msg:
                    raise Exception('make error! status_msg={}'.format(status_msg))
                time.sleep(1)
            if self.coffee_driver.query_status().get('system_status') != CoffeeMachineStatus.idle:
                # 制作完成后，咖啡机必须为idle状态
                raise CoffeeError('Sorry coffee making failed, status is {}'.format(
                    self.coffee_driver.query_status()))
            # CoffeeInterface.post_use('coffee', composition.get('coffee').get('coffee_make').get('volume'))
        except Exception as e:
            raise e
            raise CoffeeError(str(e))
        # self.goto_temp_point(which, x=coffee_pose.x - 300, wait=False, speed=pose_speed)  # 做完咖啡回退，准备接糖浆等配料

    def make_foam_demo(self):
        """
        右手先到龙头处接奶，再到奶泡机打发
        composition: {'fresh_dairy' :150} or {'plant_based': 150}
        """
        pose_speed = 400  # 800
        if not ser.isOpen():
            ser.open()
            time.sleep(1)
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        self.goto_initial_position_direction(which, tap_pose.roll, wait=True, speed=pose_speed)
        take_milk_pose = deepcopy(tap_pose)
        take_milk_pose.z = 110

        # 龙头下方位置
        open_dict = {}  # {'tap_0': 150} arduino打开水泵需要字段
        first_run_flag = True
        self.thread_lock.acquire()
        if first_run_flag:
            self.goto_point(which, take_milk_pose, wait=False, speed=300)  # 运动到龙头下方位置
            self.goto_temp_point(which, x=take_milk_pose.x + 15, speed=300, wait=True)  # 向上运动，准备接奶
            char = "c"

            if not ser.isOpen():
                ser.open()
                time.sleep(1)

            ser.write(char.encode('utf-8'))
            logger.info('sent {}'.format(char))
            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            time.sleep(6)
            char = "0"
            if not ser.isOpen():
                ser.open()
                time.sleep(1)
            ser.write(char.encode('utf-8'))

            if ser.isOpen():
                time.sleep(0.5)
                ser.close()

            first_run_flag = False
        # machine_config = CoffeeInterface.get_machine_config(name)
        # machine_name = '{}_{}'.format(machine_config.get('machine'), machine_config.get('num'))
        # open_dict[machine_name] = quantity
        # logger.info('prepare open {} for {} ml'.format(machine_name, quantity))
        # logger.debug('arduino open_dict = {}'.format(open_dict))
        # offeeInterface.post_use(name, quantity)
        # self.arduino.open_port(open_dict) # todo 控制arduino打开接奶，以实际测试为准
        time.sleep(2)  # 模拟等待接配料时间
        if not first_run_flag:  # 机械臂有动作
            self.goto_point(which, take_milk_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            make_foam_pose = deepcopy(self.env.machine_config.foam_machine.pose)
            make_foam_pose.roll = self.get_xy_initial_angle(which, make_foam_pose.x, make_foam_pose.y)
            make_foam_pose.z = 150  # 奶泡机上方位置
            self.goto_point(which, make_foam_pose, wait=False, speed=pose_speed)  # 运动到奶泡机上方位置
            self.goto_temp_point(which, z=65, wait=True, speed=pose_speed)  # 向下移动，准备制作奶泡
            time.sleep(45)  # 30  # 等待制作奶泡，前一步wait必为True
            self.goto_temp_point(which, z=make_foam_pose.z, wait=True, speed=pose_speed)  # 制作完成，提起奶泡杯
        self.thread_lock.release()

    def take_coffee_machine(self, composition: dict, cmd_sent=False):
        """
        "latte": {
            "count": 60,
            "coffee_make": {"drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
                        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
                        "coffeeMilkTogether": 0, "adjustOrder": 1}
            }
        """
        logger.info('take_coffee_machine with composition = {}'.format(composition))
        pose_speed = 600  # 800
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.left
        # 咖啡机出口高度 - （杯子高度 - 夹爪抓杯高度）-3cm
        coffee_pose.z = coffee_pose.z - (cup_config.high - cup_config.pose.z) - 50
        coffee_pose.roll = self.get_xy_initial_angle(which, coffee_pose.x, coffee_pose.y)
        if composition:
            # self.coffee_thread.pause()
            # self.goto_initial_position_direction(which, 0, wait=True, speed=400)  # 运动回零点，朝向咖啡机方向
            self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
            for name, config in composition.items():
                try:
                    make_dict = config.get('coffee_make')
                    if not cmd_sent:
                        # pass
                        # 已经在别处发过指令了
                        self.coffee_driver.make_coffee_from_dict(make_dict)

                    self.coffee_driver.wait_until_completed()
                    # time.sleep(3)
                except Exception as e:
                    # AudioInterface.gtts(str(e))
                    if COFFEE_STATUS.get('error_msg', {}).get('11') in str(e):
                        CoffeeInterface.bean_out()
                    # self.goto_temp_point(which, z=coffee_pose.z + 9, wait=False, speed=200)
                    self.goto_temp_point(which, y=coffee_pose.y - 200, wait=False, speed=200)  # 有报错也要先回退
                    self.stop()
                    logger.error(str(e))
                    raise e
            # self.coffee_thread.proceed()
            # self.goto_temp_point(which, z=coffee_pose.z + 9, wait=False, speed=200)
            self.goto_temp_point(which, y=coffee_pose.y - 200, wait=False, speed=200)  # 做完咖啡回退

    def take_from_bucket(self, composition: dict):
        logger.info('take_from_bucket with composition = {}'.format(composition))
        pose_speed = 300  # 800
        which = Arm.left
        for name, quantity in composition.items():  # 必须有这个遍历，这样传入空值时机械臂才不会运动
            bucket_config = [i for i in self.env.machine_config.bucket if i.name == name][0]  # coffee_machine.yml的bucket里面进行设置
            bucket_pose = deepcopy(bucket_config.pose)
            bucket_pose.roll = self.get_xy_initial_angle(which, bucket_pose.x, bucket_pose.y)
            self.goto_initial_position_direction(which, bucket_pose.roll, wait=True, speed=pose_speed)  # 运动回零点，朝向保温桶方向
            self.goto_gripper_position(which, 470, wait=True)
            temp_pose = deepcopy(bucket_pose)
            temp_pose.y -= 100
            self.goto_point(which, temp_pose, wait=True, speed=pose_speed)

            self.goto_point(which, bucket_pose, wait=True, speed=pose_speed)
            time.sleep(3)
            self.goto_temp_point(which, y=bucket_pose.y - 100, wait=True, speed=pose_speed)
            self.goto_initial_position_direction(which, bucket_pose.roll, wait=True, speed=pose_speed)
            self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def take_ingredients(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))
        pose_speed = 400  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = arm
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        take_pose = deepcopy(tap_pose)
        if which == Arm.left:
            take_pose.x -= 10
            take_pose.z = 200  # 龙头下方位置
        else:
            take_pose.z = 170
        first_run_flag = True
        self.thread_lock.acquire()
        move = False
        for name, quantity in composition.items():
            if first_run_flag:
                self.goto_initial_position_direction(which, tap_pose.roll, wait=False, speed=pose_speed)
                self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                # self.goto_temp_point(which,x=take_pose.x + 20, speed=pose_speed, wait=True)
                # middle_pose = deepcopy(take_pose)
                # middle_pose.x -= 175
                # middle_pose.y += math.tan(take_pose.roll * math.pi / 180) * 175
                # self.goto_point(which, middle_pose, wait=False, speed=pose_speed)  # 运动到龙头斜后方位置
                # take_pose.x += 20
                # self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头位置
                first_run_flag = False
                move = True
            CoffeeInterface.post_use(name, quantity)
        logger.debug('arduino open_dict = {}'.format(composition))
        sea_salt_foam_count = composition.pop('sea_salt_foam', 0)  # 尝试从字典里删除海盐奶盖相关内容,没有就设为0
        vanilla_syrup_count = composition.pop('vanilla_syrup', 0)
        vanilla_cream_count = composition.pop('vanilla_cream', 0)
        self.arduino.open_port_together(composition)  # 先根据删除后的字典打开相应龙头
        if sea_salt_foam_count > 0:
            # 如果大于0，说明要接奶盐奶盖
            self.arduino.open_port_together({'sea_salt_foam': sea_salt_foam_count})  # 再接海盐奶盖

        if vanilla_syrup_count > 0:
            # 如果大于0，说明要接奶盐奶盖
            self.arduino.open_port_together({'vanilla_syrup': vanilla_syrup_count})  # 再接海盐奶盖

        if vanilla_cream_count > 0:
            # 如果大于0，说明要接奶盐奶盖
            self.arduino.open_port_together({'vanilla_cream': vanilla_cream_count})  # 再接海盐奶盖

            # time.sleep(2)  # 模拟等待接配料时间
        if move:  # 机械臂有动作
            # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
            self.goto_temp_point(which, x=take_pose.x - 100, wait=False, speed=200)
            if which == Arm.left:
                self.goto_initial_position_direction(which, 0, wait=True, speed=200)  # 运动回零点
        self.thread_lock.release()

    def check_sensor(self):
        self.arduino.read_line()

    def take_ingredients_foam(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))
        pose_speed = 500  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = arm
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
        self.goto_initial_position_direction(which, tap_pose.roll, wait=True, speed=pose_speed)
        take_pose = deepcopy(tap_pose)
        take_pose.z = 110
        first_run_flag = True
        self.thread_lock.acquire()
        for name, quantity in composition.items():
            if first_run_flag:
                self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                # self.goto_temp_point(which,x=take_pose.x + 20, speed=pose_speed, wait=True)
                # middle_pose = deepcopy(take_pose)
                # middle_pose.x -= 175
                # middle_pose.y += math.tan(take_pose.roll * math.pi / 180) * 175
                # self.goto_point(which, middle_pose, wait=False, speed=pose_speed)  # 运动到龙头斜后方位置
                # take_pose.x += 20
                # self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头位置
                first_run_flag = False
            CoffeeInterface.post_use(name, quantity)
        logger.debug('arduino open_dict = {}'.format(composition))
        self.arduino.open_port_together(composition)  # todo 控制arduino打开接奶，以实际测试为准
        # time.sleep(5)  # 模拟等待接配料时间
        # if not first_run_flag:  # 机械臂有动作
        #     # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 向下移动，准备离开龙头
        #     if which == Arm.left:
        #         self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)  # 运动回零点
        self.thread_lock.release()

    def put_hot_cup(self, cup=None):
        logger.info('put_hot_cup')
        pose_speed = 200
        put_config = [i for i in self.env.machine_config.put if i.name == define.CupName.hot_cup][0]
        put_pose = deepcopy(put_config.pose)
        which = self.env.left_or_right(put_pose.y)  # Arm.left
        weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())

        # self.left.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
        # self.safe_set_state(Arm.left, 0)
        # time.sleep(0.1)

        temp_pose = deepcopy(put_pose)
        temp_pose.x -= 300
        self.goto_point(which, temp_pose, speed=pose_speed, wait=True)  # 放杯位置后上方
        self.goto_point(which, put_pose, wait=True, speed=pose_speed)  # 运动到放杯位置上方
        # self.goto_temp_point(which, z=put_pose.z - 125, wait=True, speed=40)  # 运动到放杯位置 z-=33
        if cup == 'cold_cup':
            self.goto_temp_point(which, z=put_pose.z - 135, wait=True, speed=40)  # 运动到放杯位置 z-=33
        else:
            self.goto_temp_point(which, z=put_pose.z - 100, wait=True, speed=40)
        self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)  # 张开夹爪
        self.goto_temp_point(which, x=put_pose.x - 400, wait=False, speed=400)  # 放完向后退
        self.goto_point(which, self.initial_position(which), wait=False, speed=400)  # 回零点
        self.change_adam_status(AdamTaskStatus.idle)

    # right actions
    def take_cold_cup(self):
        """
        右手取冷咖杯子，一旦取杯子就认为开始做咖啡了
        """
        pose_speed = 200
        logger.info('take_cold_cup')

        self.change_adam_status(AdamTaskStatus.making)
        cup_config = self.get_cup_config(define.CupName.cold_cup)
        self.current_cup_name = cup_config.name
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)

        which = Arm.right

        weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())

        self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
        self.safe_set_state(Arm.right, 0)
        time.sleep(0.1)

        def take_cup():
            # 计算旋转手臂到落杯器的角度
            cup_pose.x = cup_pose.x + 500
            cup_pose.y = cup_pose.y + 65
            cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)
            up_take_pose = deepcopy(cup_pose)

            up_take_pose.z = 250  # 250
            self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)
            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 先张开夹爪
            self.goto_point(which, up_take_pose, speed=pose_speed, wait=False)  # 运动到抓杯位置上方
            self.goto_tool_position(which, yaw=180, speed=1500, wait=True)  # 翻转夹爪
            self.goto_temp_point(which, z=cup_pose.z, speed=pose_speed, wait=False)  # 运动到抓杯位置
            self.goto_gripper_position(which, cup_config.clamp, wait=True)  # 闭合夹爪
            logger.info('take cup with clamp = {}'.format(cup_config.clamp))
            logger.info('take cup pos----------'.format(up_take_pose))
            self.env.one_arm(which).set_collision_sensitivity(cup_config.collision_sensitivity)  # 设置灵敏度，根据实际效果确定是否要注释
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)
            self.goto_temp_point(which, z=up_take_pose.z, speed=pose_speed, wait=False)  # 向上拔杯子
            # CoffeeInterface.post_use(define.CupName.cold_cup, 1)  # 冷咖杯子数量-1
            self.goto_tool_position(which, yaw=-180, speed=1500, wait=True)  # 再次翻转夹爪
            self.goto_temp_point(which, y=up_take_pose.y + 150, speed=pose_speed, wait=True)
            # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)
            #  todo 运动到arduino检测位置, wait=True

        def take_cup_alex():
            cup_pose.x = cup_pose.x + 203
            cup_pose.y = cup_pose.y + 50

            cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)

            self.goto_initial_position_direction(which, cup_pose.roll, wait=False)

            self.goto_gripper_position(which, self.env.gripper_open_pos)

            self.right.set_tool_position(yaw=180, speed=1000, wait=True)

            current_position = self.current_position(which)
            current_position.x, current_position.y, current_position.z = cup_pose.x, cup_pose.y, cup_pose.z
            self.goto_point(which, current_position, wait=False, speed=1000)

            self.goto_gripper_position(which, cup_config.clamp, wait=True)
            position1 = self.current_position(which)
            position1.z += 200
            # take cup, set tcp load bigger
            self.goto_point(which, position1, wait=True, speed=1000)
            # recover tcp load

            self.right.set_tool_position(yaw=-180, speed=1000, wait=False)

        take_cup_alex()
        self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)

    def take_foam_cup(self):
        logger.info('take_foam_cup')
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 400  # 800
        which = Arm.right

        take_pose.roll = self.get_xy_initial_angle(which, take_pose.x, take_pose.y)
        self.goto_initial_position_direction(which, take_pose.roll, wait=True, speed=pose_speed)  # 转向奶泡杯方向
        self.goto_gripper_position(which, self.env.gripper_open_pos)  # 张开夹爪
        self.goto_tool_position(which, yaw=180, speed=1500, wait=True)
        self.goto_temp_point(which, x=take_pose.x, y=take_pose.y, z=take_pose.z, speed=pose_speed, wait=False)
        # self.goto_point(which, take_pose, wait=False, speed=pose_speed)  # 运动到奶泡杯位置
        self.goto_gripper_position(which, foam_cup_config.clamp, wait=True)  # 闭合夹爪
        self.goto_temp_point(which, z=take_pose.z + 50, speed=pose_speed, wait=False)  # 向上运动5cm
        self.goto_tool_position(which, yaw=-180, speed=1500, wait=True)

    def take_ice(self, level):
        """
        level: no_ice: 0, light: 1, more: 1.5.
        see coffee_machine.yaml -> task_option for more detail
        """
        logger.info('take_ice with level = {}'.format(level))
        if level > 0:
            pose_speed = 500
            ice_pose = deepcopy(self.env.machine_config.ice_maker[0].pose)
            which = Arm.right
            ice_pose.roll = self.get_xy_initial_angle(which, ice_pose.x, ice_pose.y)
            middle_pose = adam_schema.Pose.list_to_obj([0, -900, 250, ice_pose.roll, 90, 0])

            # self.goto_point(which, middle_pose, wait=True, speed=pose_speed)  # 运动到过渡位置 wait = False
            self.goto_point(which, ice_pose, wait=True, speed=pose_speed)  # 运动到过渡位置
            delay_time = 9  # 接冰停顿时间 
            if level == 1.5:
                time.sleep(4)
            else:
                time.sleep(delay_time * level)  # 等待接冰，前一步必为wait=True
            self.goto_point(which, middle_pose, wait=False, speed=pose_speed)  # 返回到过渡位置
            self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 返回工作零点

    def release_ice(self):
        logger.info('clean_ice with task status={}'.format(self.task_status))
        if self.task_status == AdamTaskStatus.idle:
            pose_speed = 500
            which = Arm.right
            release_ice_pose = deepcopy(self.env.machine_config.ice_maker[0].pose)
            release_ice_pose.z += 20
            release_ice_pose.y -= 10  # 以实际为准
            release_ice_pose.roll = self.get_xy_initial_angle(which, release_ice_pose.x, release_ice_pose.y)

            middle_pose = adam_schema.Pose.list_to_obj([0, -900, 250, release_ice_pose.roll, 90, 0])

            self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 运动到工作零点
            self.goto_point(which, middle_pose, wait=False, speed=pose_speed)  # 运动到过渡位置
            self.goto_point(which, release_ice_pose, wait=True, speed=pose_speed)  # 触碰铁片
            self.goto_point(which, middle_pose, wait=False, speed=pose_speed)  # 返回到过渡位置
            self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 返回工作零点
            init_angle = [-132, 8.7, -34.5, 45.9, 42.8, 38.7]
            self.goto_angles(which, adam_schema.Angles.list_to_obj(init_angle), wait=True)

    def dip(self, composition):
        """
        沾糖粉动作
        """
        logger.info('dip with composition = {}'.format(composition))
        # todo dip actions

    def make_foam(self, composition: dict):
        """
        右手先到龙头处接奶，再到奶泡机打发
        composition: {"foam": {"count": 450, "foam_time": 45}}
        """
        logger.info('make_foam with composition = {}'.format(composition))
        pose_speed = 400  # 800
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
        which = Arm.right
        tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)

        take_milk_pose = deepcopy(tap_pose)
        take_milk_pose.z = 110

        if composition:
            self.goto_initial_position_direction(which, tap_pose.roll, wait=True, speed=pose_speed)
            foam_composition = composition.get('foam', {}).get('foam_composition', {})  # 从字典获取奶泡的原料配方及数量
            self.take_ingredients_foam(Arm.right, foam_composition)  # 去龙头接牛奶和糖浆
            make_foam_pose = deepcopy(self.env.machine_config.foam_machine.pose)
            make_foam_pose.roll = self.get_xy_initial_angle(which, make_foam_pose.x, make_foam_pose.y)
            make_foam_pose.z = 150  # 奶泡机上方位置
            self.goto_point(which, make_foam_pose, wait=True, speed=pose_speed)  # 运动到奶泡机上方位置
            self.goto_temp_point(which, z=72, wait=True, speed=pose_speed)  # 向下移动，准备制作奶泡
            self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)
            foam_time = composition.get('foam', {}).get('foam_time', 45)  # 从字典获取奶泡的制作时间
            time.sleep(foam_time)  # 30  # 等待制作奶泡，前一步wait必为True
            self.goto_gripper_position(which, 100, wait=True)
            self.goto_temp_point(which, z=make_foam_pose.z, wait=True, speed=200)  # 制作完成，提起奶泡杯

    def clean_foamer(self):
        """清洗调酒壶"""
        logger.info('clean_foamer')
        pose_speed = 400

        pose = deepcopy(self.env.machine_config.shaker.pose.clean)
        pose.roll = self.get_xy_initial_angle(Arm.right, pose.x, pose.y)
        pose.x -= 50
        self.goto_temp_point(Arm.right, x=pose.x, y=0, z=500, wait=False, speed=pose_speed)
        # self.goto_temp_point(Arm.right, roll = pose.roll, wait=True, speed=pose_speed)
        self.goto_temp_point(Arm.right, x=pose.x, y=pose.y, z=pose.z, wait=False, speed=pose_speed)
        # self.goto_initial_position_direction(Arm.right, pose.roll, wait=True, speed=pose_speed)
        # self.goto_point(Arm.right, pose, wait=True, speed=pose_speed)  # 运动到清洗位置上方
        # self.goto_tool_position(Arm.right, yaw=180, speed=800, wait=True)  # 翻转夹爪 #speed = 1000

        self.goto_temp_point(Arm.right, x=580, z=130, wait=True, speed=pose_speed)  # 下压
        self.arduino.arduino.open()
        self.arduino.arduino.send_one_msg('9')  # todo 此处不确定是否发送字符p
        self.arduino.arduino.close()

        self.goto_temp_point(Arm.right, y=10, wait=True, speed=pose_speed)  # 下压
        self.goto_temp_point(Arm.right, y=-20, wait=True, speed=pose_speed)
        self.goto_temp_point(Arm.right, x=590, y=-10, wait=True, speed=pose_speed)
        self.goto_temp_point(Arm.right, x=570, wait=True, speed=pose_speed)
        self.goto_temp_point(Arm.right, x=580, wait=True, speed=pose_speed)

        time.sleep(1)
        self.arduino.arduino.open()
        self.arduino.arduino.send_one_msg('0')
        self.arduino.arduino.close()

        self.goto_temp_point(Arm.right, x=490, z=200, wait=True, speed=pose_speed)  # 清洗完向上提起奶泡杯，防止奶泡杯转动中打到桌面
        time.sleep(3)
        self.goto_tool_position(Arm.right, yaw=180, x=0, speed=800, wait=True)

    def put_foam_cup(self):
        logger.info('put_foam_cup')
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 600  # 800
        which = Arm.right

        take_pose.roll = self.get_xy_initial_angle(which, take_pose.x, take_pose.y)
        self.goto_initial_position_direction(which, take_pose.roll, wait=True, speed=pose_speed)  # 转向奶泡杯方向
        # self.goto_temp_point(which, x=take_pose.x, y = take_pose.y, z=take_pose.z, roll=take_pose.roll, speed=pose_speed, wait=True)

        temp_pose = deepcopy(take_pose)
        temp_pose.z += 200
        temp_pose.pitch += 2
        # self.goto_temp_point(which, x=temp_pose.x, y = temp_pose.y, z=temp_pose.z, speed=pose_speed, wait=True)
        self.goto_point(which, temp_pose, wait=True, speed=pose_speed)  # 运动到奶泡杯位置
        self.goto_tool_position(which, yaw=180, speed=1500, wait=True)
        self.goto_temp_point(which, x=take_pose.x - 1, y=take_pose.y, z=take_pose.z, speed=pose_speed, wait=True)
        # self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到奶泡杯位置
        self.goto_gripper_position(which, self.env.gripper_open_pos)  # 张开夹爪
        self.goto_temp_point(which, z=take_pose.z + 150, speed=pose_speed, wait=False)
        self.goto_tool_position(Arm.right, yaw=-180, x=0, speed=800, wait=True)
        self.goto_initial_position_direction(Arm.right, 0, wait=False, speed=pose_speed)  # 回零点

    def put_cold_cup(self):
        """
        放杯子，一旦杯子放完就认为制作流程结束，adam状态并未空闲
        """
        logger.info('put_cold_cup')
        pose_speed = 200
        put_config = [i for i in self.env.machine_config.put if i.name == define.CupName.cold_cup][0]
        put_pose = deepcopy(put_config.pose)
        which = self.env.left_or_right(put_pose.y)  # Arm.right

        temp_pose = deepcopy(put_pose)
        temp_pose.x -= 400
        self.goto_point(which, temp_pose, speed=pose_speed, wait=True)  # 放杯位置后上方
        # self.goto_gripper_position(which, 270, wait=True)
        self.goto_point(which, put_pose, wait=True, speed=pose_speed)  # 运动到放杯位置上方
        self.goto_temp_point(which, z=put_pose.z - 50, wait=True, speed=40)  # 运动到放杯位置
        self.goto_gripper_position(which, self.env.gripper_open_pos, wait=False)  # 张开夹爪
        self.goto_temp_point(which, x=put_pose.x - 400, wait=False, speed=pose_speed)  # 放完向后退
        self.goto_point(which, self.initial_position(which), wait=True, speed=pose_speed)  # 回零点
        self.change_adam_status(AdamTaskStatus.idle)

    # action with left arm & right arm
    def pour(self, action):
        """倒入杯中"""
        logger.info('pour')
        pose_speed = 200
        roll = self.get_xy_initial_angle(Arm.right, 550, -100)
        try:
            if action == 'ice':  # 目前都是ice
                left_pose = adam_schema.Pose.list_to_obj([470, -7, 400, 90, 90, 0])  # x = 430, y=0, z = 340
                self.goto_point(Arm.left, left_pose, wait=True, speed=pose_speed)  # 左手位置
                tcp_offset = list(self.adam_config.gripper_config['pour_ice'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)  # 右手根据调酒壶设置偏移和载重
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
                self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([495, -55, 500, roll, 90, 0]),
                                speed=pose_speed, wait=False)  # 右手位置 x = 465, y = -70, z=420
                self.goto_tool_position(which=Arm.right, x=0, y=50, z=0, yaw=-178, speed=100,
                                        wait=True)  # 倒入杯中，边转边往内 y was 85 speed was 400 yaw = -125
                curr_pose = self.right.position
                self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] - 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] - 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] - 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] - 10, speed=200, wait=True)
                # self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=200, wait=True)
                # time.sleep(6)
                tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['default'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)  # 恢复默认偏移和载重
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
                # self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([520, -100, 490, roll, 90, 0]), wait=True, speed=500)  # 回到右手位置
            elif action == 'wine':
                left_pose = adam_schema.Pose.list_to_obj([500, 0, 340, 90, 90, 0])
                self.goto_point(Arm.left, left_pose, wait=False, speed=pose_speed)
                tcp_offset = list(self.adam_config.gripper_config['pour_wine'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['pour_wine'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['pour_wine'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                time.sleep(0.5)
                self.right.set_state(0)
                time.sleep(0.5)
                self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([455, 0, 720, -90, 90, 0]), wait=True,
                                speed=pose_speed)

                self.goto_tool_position(Arm.right, y=-30, yaw=65, speed=pose_speed, wait=True)
                self.goto_tool_position(Arm.right, x=-20, yaw=50, speed=pose_speed, wait=True)
                curr_pose = self.right.position
                curr_pose[2] += 30
                self.right.set_position(*curr_pose, speed=pose_speed, wait=False)
                curr_pose[2] -= 30
                self.right.set_position(*curr_pose, speed=pose_speed, wait=False)
                curr_pose[2] += 30
                self.right.set_position(*curr_pose, speed=pose_speed, wait=False)
                curr_pose[2] -= 30
                self.right.set_position(*curr_pose, speed=pose_speed, wait=True)

                self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([455, 0, 720, -90, 90, 0]), wait=True,
                                speed=pose_speed)
        finally:
            logger.info('set back tcp_offset to default')
            default_tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(
                self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
            self.right.set_tcp_offset(offset=default_tcp_offset)
            self.right.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)
            time.sleep(0.5)
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)

    def take_wine(self, formula, iced_flag="1"):
        if formula in define.Material.cocktail:
            # if(ser2.isOpen() == True):
            #     ser2.close() 
            # if(ser2.isOpen() == False): #Turn on serial port.
            #     ser2.open()

            # if temp_formula := [i for i in self.material.cocktail if i.name ==
            #  formula]:
            #     config = deepcopy(temp_formula[0])
            # else:
            #     raise Exception('no formula={} in material.yml'.format(formula))
            # # {'wine_name':20}
            # composition = {i.split(',')[0]: float(i.split(',')[-1].strip()) for i in config.composition} #{valve name: maximum volume}
            # logger.info('composition = {} '.format(composition))
            first_run_flag = True
            # open_thread = []

            # #comp_val = list(composition.values())
            # comp_key = list(composition.keys()) #Gather the key names in the dict composition. The keys and ingredient names will be changed to the valve names. The valve names will be used to turn on/off the valves.
            # comp_length = len(comp_key) #Find the length of the list and use that for the loop.

            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            # if iced_flag == '0':
            #     left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.start)

            # elif iced_flag == '1':
            #     left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.iced)
            formula = "Iced coffee"
            if str(formula) in ['Iced coffee', 'Iced coffee with milk', 'Iced coffee with sugar', 'Iced coffee with sugar and ice']:
                left_gpio_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
            elif str(formula) == "Orange Juice" or str(formula) == "Apple Juice":
                left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.start)
            elif str(formula) == "Tea":
                left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.iced)
            elif str(formula) == "Lemonade":
                left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.iced)
            elif str(formula) == "Green tea":
                left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.iced)

            which = self.env.left_or_right(left_gpio_pose.y)

            left_gpio_pose.roll = self.get_xy_initial_angle(which, left_gpio_pose.x, left_gpio_pose.y)
            if first_run_flag:
                first_run_flag = False
                left_gpio_pose.roll = 0
                # self.goto_initial_position_direction(Arm.left, left_gpio_pose.roll, wait=False)
                if str(formula) in ['Iced coffee', 'Iced coffee with milk', 'Iced coffee with sugar', 'Iced coffee with sugar and ice']:
                    # left_gpio_pose.y += 345
                    left_gpio_pose.x += 30
                    left_gpio_pose.z += 40
                elif str(formula) == "Orange Juice":
                    left_gpio_pose.y -= 20
                    left_gpio_pose.x += 50
                    left_gpio_pose.z += 45

                elif str(formula) == "Apple Juice":
                    left_gpio_pose.y -= 1
                    left_gpio_pose.x += 50
                    left_gpio_pose.z += 70


                elif str(formula) == "Tea":
                    left_gpio_pose.y += 80
                    left_gpio_pose.z += 90
                    left_gpio_pose.x += 40
                elif str(formula) == "Lemonade":
                    left_gpio_pose.y += 120
                    left_gpio_pose.z += 90
                    left_gpio_pose.x += 40
                elif str(formula) == "Green tea":
                    left_gpio_pose.y += 20
                    left_gpio_pose.z += 70
                    left_gpio_pose.x += 50

                left_gpio_pose.x -= 30
                left_gpio_pose.z -= 10
                self.goto_point(which, left_gpio_pose, wait=True)
                left_gpio_pose.x += 130
                left_gpio_pose.z += 50
                # -------------------------
            # ---------------------------------------------------------------------------------------------------------------------------------------------------------
            # starts moter
            # if not ser2.isOpen():
            #     ser2.open()

            if str(formula) in ['Iced coffee', 'Iced coffee with sugar']:
                char = "r"
                self.arduino.arduino.send_one_msg(char)  # 线程结束关闭所有arduino

                time.sleep(2)
                self.arduino.arduino.send_one_msg(char)  # 线程结束关闭所有arduino

                # oj = 'm'
                # ser2.write(oj.encode('utf-8'))
                # #logger.info('sent {}'.format(coffee))
                # time.sleep(3.3)
                # ser2.write(oj.encode('utf-8'))
                # time.sleep(1.5)


            elif str(formula) in ['Iced coffee with milk', 'Iced coffee with sugar and ice']:
                time.sleep(1)
                milk = 'o'
                coffee = 'm'

                ser2.write(milk.encode('utf-8'))
                time.sleep(.3)

                ser2.write(coffee.encode('utf-8'))

                # logger.info('sent {}'.format(milk))
                time.sleep(.3)
                ser2.write(milk.encode('utf-8'))
                time.sleep(2.1)

                ser2.write(coffee.encode('utf-8'))
                cancel = '0'
                time.sleep(1)

                ser2.write(cancel.encode('utf-8'))

            # if ser2.isOpen():
            #     time.sleep(0.5)
            #     ser2.close()    

            # self.goto_initial_position_direction(which, 0, wait=False, speed = 200)
        elif formula in define.Material.red_wine:
            # red wine
            open_thread = []
            for red_wine in self.env.machine_config.gpio.no_gas.outlet.red_wine:
                if red_wine.name == formula:
                    left_gpio_pose = deepcopy(self.env.machine_config.gpio.no_gas.start)
                    left_gpio_pose.roll = self.get_xy_initial_angle(Arm.left, left_gpio_pose.x, left_gpio_pose.y)
                    self.goto_initial_position_direction(Arm.left, left_gpio_pose.roll, wait=False)
                    self.goto_point(Arm.left, left_gpio_pose, wait=True)
                    which = red_wine.gpio.split(',')[0].strip()
                    number = int(red_wine.gpio.split(',')[1].strip())
                    delay_time = red_wine.capacity / red_wine.speed
                    logger.info('open {} arm {} gpio={} for {} seconds'.format(
                        which, red_wine.name, red_wine.gpio, delay_time))
                    WineInterface.post_use(red_wine.name, red_wine.capacity)
                    open = threading.Thread(targer=self.open_gpio, args=(which, number, delay_time))
                    open_thread.append(open)
                    # time.sleep(0.5)
            for t in open_thread:
                t.start()
            for t in open_thread:
                t.join()
        elif formula in define.Material.gas_water:
            # gas water
            # 'Cola no-ice' -> 'Cola'
            formula = formula.replace('no-ice', '').strip()
            for i, gas in enumerate(self.env.machine_config.gpio.gas.outlet):
                if gas.name == formula:
                    logger.info('open {} switch={}'.format(gas.name, i))
                    self.take_gas_water(formula)
                    time.sleep(0.5)
        # lcode, rcode = self._goto_work_zero_use_set_position_with_true()
        # if lcode != 0 or rcode != 0:  # move has error, stop adam and prepare for roll back
        #     self.stop()
        #     # self.roll()

    def pass_cup_old(self, action, switch=0):
        logger.info('pass_cup')
        speed = 'slow_take'
        if action == 'from_right':
            self.goto_gripper_position(Arm.left, 800, wait=True)

            def left_action():
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 340, 30, 90, 0]), wait=True,
                                speed=300)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 350, 90, 90, 0]), wait=False,
                                speed=200)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, -15, 330, 90, 90, 0]), wait=True,
                                speed=200)  # y=0
                while True:
                    logger.debug(" TEST WHILE LOOP")
                    current_position = self.current_position(Arm.left)
                    cur_pos = str(current_position)
                    list1 = cur_pos.split(" ")
                    list2 = list1[1].split("=")
                    left_y = float(list2[1])
                    if left_y == -15:
                        self.goto_gripper_position(Arm.left, 390, wait=True)
                        self.goto_gripper_position(Arm.right, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(1)

                if is_grabbed == 1:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False,
                                    speed=300)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False)
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False,
                                    speed=300)
                    self.goto_initial_position_direction(Arm.left, 0, wait=False)

            def right_action():
                if switch == 0:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 290, -30, 90, 0]), wait=False,
                                    speed=300)
                    # self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 290, -30, 90, 0]), wait=False,
                    #               speed=400)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 290, -90, 90, 0]), wait=False,
                                    speed=300)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 290, -90, 90, 0]), wait=True,
                                    speed=300)  # y = 0

                if switch == 1:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 315, -30, 90, 0]), wait=False,
                                    speed=400)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 315, -90, 90, 0]), wait=False,
                                    speed=400)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 315, -90, 90, 0]), wait=True,
                                    speed=400)

            thread_list = [threading.Thread(target=left_action), threading.Thread(target=right_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

        # FROM LEFT TO RIGHT
        if action == 'from_left':
            speed = 200
            # self.goto_gripper_position(Arm.left, 240, wait=True)
            self.goto_gripper_position(Arm.right, 800, wait=False)

            def right_action():
                # self.goto_initial_position_direction(Arm.right, 0, wait=False)  # Return to initial position

                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 315, -30, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 315, -90, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 315, -90, 90, 0]), wait=True,
                                speed=speed)

                # time.sleep(.5)
                # while True:
                #     if is_grabbed == 1:
                #         self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=True, speed = speed)
                #         self.goto_initial_position_direction(Arm.right, 0, wait=False)
                #         break
                #     else:
                #         time.sleep(1)

            def left_action():
                # self.goto_initial_position_direction(Arm.left, 0, wait=False)  # Return to initial position

                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 280, 30, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 280, 90, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 0, 280, 90, 90, 0]), wait=True,
                                speed=speed)

                while True:
                    logger.debug(" TEST WHILE LOOP")

                    current_position = self.current_position(Arm.right)
                    cur_pos = str(current_position)

                    list1 = cur_pos.split(" ")

                    list2 = list1[1].split("=")

                    right_y = float(list2[1])
                    if right_y == -0.0:
                        self.goto_gripper_position(Arm.right, 330, wait=True)
                        self.goto_gripper_position(Arm.left, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(1)

                if is_grabbed == 1:
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False,
                                    speed=speed)
                    self.goto_initial_position_direction(Arm.left, 0, wait=False)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False,
                                    speed=speed)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False, speed=200)

            thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

    def pass_cup(self, action, switch=0):
        speed = 299

        if action == 'from_right':
            self.goto_gripper_position(Arm.left, 800, wait=True)

            # self.goto_gripper_position(Arm.right, 81, wait=True)
            # switch = 0
            def left_action():
                # self.goto_initial_position_direction(Arm.left, 0, wait=False)  # Return to initial position
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 280, 30, 90, 0]), wait=False, speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 280, 90, 90, 0]), wait=False, speed=speed)

                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, -7, 285, 90, 90, 0]), wait=True, speed=speed)

                while True:
                    logger.debug(" TEST WHILE LOOP")

                    current_position = self.current_position(Arm.right)
                    cur_pos = str(current_position)

                    list1 = cur_pos.split(" ")

                    list2 = list1[1].split("=")

                    right_y = float(list2[1])
                    if right_y == 0.0:
                        time.sleep(.1)
                        self.goto_gripper_position(Arm.left, 340, wait=True)
                        self.goto_gripper_position(Arm.right, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(.1)

                if is_grabbed == 1:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False, speed=speed)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False)
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False, speed=speed)
                    # self.goto_initial_position_direction(Arm.left, 0, wait=False)

            def right_action():
                # self.goto_initial_position_direction(Arm.right, 0, wait=False)  # Return to initial position

                if switch == 0:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 240, -30, 90, 0]), wait=False, speed=speed)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 240, -90, 90, 0]), wait=False, speed=speed)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 240, -90, 90, 0]), wait=True, speed=speed)

                if switch == 1:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 315, -30, 90, 0]), wait=False, speed=speed)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 315, -90, 90, 0]), wait=False, speed=speed)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 315, -90, 90, 0]), wait=True, speed=speed)

            thread_list = [threading.Thread(target=left_action), threading.Thread(target=right_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

        # FROM LEFT TO RIGHT
        if action == 'from_left':

            # self.goto_gripper_position(Arm.left, 240, wait=True)
            self.goto_gripper_position(Arm.right, 800, wait=False)

            def right_action():
                # self.goto_initial_position_direction(Arm.right, 0, wait=False)  # Return to initial position

                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 240, -30, 90, 0]), wait=False, speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 240, -90, 90, 0]), wait=False, speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 240, -90, 90, 0]), wait=True, speed=speed)

                # time.sleep(.5)
                # while True:
                #     if is_grabbed == 1:
                #         self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=True, speed = speed)
                #         self.goto_initial_position_direction(Arm.right, 0, wait=False)
                #         break
                #     else:
                #         time.sleep(1)

            def left_action():
                # self.goto_initial_position_direction(Arm.left, 0, wait=False)  # Return to initial position

                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 280, 30, 90, 0]), wait=False, speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 280, 90, 90, 0]), wait=False, speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 0, 280, 90, 90, 0]), wait=True, speed=speed)

                while True:
                    logger.debug(" TEST WHILE LOOP")

                    current_position = self.current_position(Arm.right)
                    cur_pos = str(current_position)

                    list1 = cur_pos.split(" ")

                    list2 = list1[1].split("=")

                    right_y = float(list2[1])
                    if right_y == -0.0:
                        self.goto_gripper_position(Arm.right, 120, wait=True)
                        self.goto_gripper_position(Arm.left, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(1)

                if is_grabbed == 1:
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False, speed=speed)
                    self.goto_initial_position_direction(Arm.left, 0, wait=False)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False, speed=speed)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False)

            thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

    # whole make actions
    def make_hot_drink(self, formula, sweetness, milk, ice, receipt_number):
        logger.debug('start in make_hot_drink')
        composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk, ice)

        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()

        # step 1
        self.left_record.proceed()  # 记录关节位置线程开启
        self.take_cold_cup()

        # def left():
        #     self.take_wine("Green tea")

        # def right():
        #     self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=400)

        # step0_thread = [threading.Thread(target=left), threading.Thread(target=right)]
        # for t in step0_thread:
        #     t.start()
        # for t in step0_thread:
        #     t.join()

        self.pass_cup("from_right")

        # self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))  # 热饮有配料先接配料
        def left_step1():
            # self.left_record.proceed()  # 记录关节位置线程开启
            # self.take_hot_cup()
            # self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))  # 热饮有配料先接配料
            self.take_coffee_machine(composition.get(define.Constant.MachineType.coffee_machine, {}))  # 有咖啡机就去咖啡机制作

            self.take_from_bucket(composition.get(define.Constant.MachineType.bucket, {}))  # 有保温桶就去接保温桶

        def right_step1():
            self.right_record.proceed()  # 记录关节位置线程开启
            pass
            # if composition.get(define.Constant.MachineType.foam_machine):
            #     self.take_foam_cup()
            #     self.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}))  # 有奶泡机就制作奶泡

        step1_thread = [threading.Thread(target=left_step1), threading.Thread(target=right_step1)]
        for t in step1_thread:
            t.start()
        for t in step1_thread:
            t.join()
        self.check_adam_status('make_hot_drink step1')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常

        # step 2
        # if composition.get(define.Constant.MachineType.foam_machine, {}):
        #     # 有制作奶泡，需要将奶泡倒入杯中
        #     self.pour('ice')

        # 放杯子之前开始语音播报
        AudioInterface.gtts("receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))

        # step 3
        def left_step3():
            self.put_hot_cup()

        def right_step3():
            pass
            # if composition.get(define.Constant.MachineType.foam_machine, {}):
            #     # 有制作奶泡，需要清洗
            #     time.sleep(2)  # 等待2秒钟，等左手离开洗杯区域，防止洗杯时碰撞
            #     self.clean_foamer()
            #     self.put_foam_cup()

        step3_thread = [threading.Thread(target=left_step3), threading.Thread(target=right_step3)]
        for t in step3_thread:
            t.start()
        for t in step3_thread:
            t.join()
        self.check_adam_status('make_hot_drink step3')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
        self.arduino.arduino.send_one_msg('0')  # 线程结束关闭所有arduino
        self.left_record.pause()
        self.right_record.pause()

    def make_hot_drink_old(self, formula, sweetness, milk, ice, receipt_number):
        logger.debug('start in make_hot_drink')
        composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk, ice)

        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()

        # step 1
        self.left_record.proceed()  # 记录关节位置线程开启
        self.take_hot_cup()

        # self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))  # 热饮有配料先接配料
        def left_step1():
            # self.left_record.proceed()  # 记录关节位置线程开启
            # self.take_hot_cup()
            # self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))  # 热饮有配料先接配料
            self.take_coffee_machine(composition.get(define.Constant.MachineType.coffee_machine, {}))  # 有咖啡机就去咖啡机制作
            self.take_from_bucket(composition.get(define.Constant.MachineType.bucket, {}))  # 有保温桶就去接保温桶

        def right_step1():
            self.right_record.proceed()  # 记录关节位置线程开启
            if composition.get(define.Constant.MachineType.foam_machine):
                self.take_foam_cup()
                self.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}))  # 有奶泡机就制作奶泡

        step1_thread = [threading.Thread(target=left_step1), threading.Thread(target=right_step1)]
        for t in step1_thread:
            t.start()
        for t in step1_thread:
            t.join()
        self.check_adam_status('make_hot_drink step1')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常

        # step 2
        if composition.get(define.Constant.MachineType.foam_machine, {}):
            # 有制作奶泡，需要将奶泡倒入杯中
            self.pour('ice')

        # 放杯子之前开始语音播报
        AudioInterface.gtts("receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))

        # step 3
        def left_step3():
            self.put_hot_cup()

        def right_step3():
            if composition.get(define.Constant.MachineType.foam_machine, {}):
                # 有制作奶泡，需要清洗
                time.sleep(2)  # 等待2秒钟，等左手离开洗杯区域，防止洗杯时碰撞
                self.clean_foamer()
                self.put_foam_cup()

        step3_thread = [threading.Thread(target=left_step3), threading.Thread(target=right_step3)]
        for t in step3_thread:
            t.start()
        for t in step3_thread:
            t.join()
        self.check_adam_status('make_hot_drink step3')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
        self.arduino.arduino.send_one_msg('0')  # 线程结束关闭所有arduino
        self.left_record.pause()
        self.right_record.pause()

    # whole make actions

    def classic_test_arduino(self, char):
        self.arduino.arduino.send_one_msg(char)  # 线程结束关闭所有arduino

    def make_cold_latte(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.take_ingredients_demo()  # milk from treacle
        self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)
        self.pass_cup("from_right")

        def right_action():
            self.take_foam_cup()
            self.make_foam_demo()

        def left_action():
            self.take_coffee_machine_espresso()  # espresso
            self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)  # 做完咖啡回退，准备接糖浆等配料

        # self.take_coffee_machine_demo()#hot milk
        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        # self.take_coffee_machine_demo_make()#espresso
        # self.take_foam_cup()
        # self.make_foam_demo()
        self.pour("ice")
        self.put_hot_cup()
        self.clean_foamer()
        self.put_foam_cup()

    def make_cold_brew(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.take_ingredients_cold_brew()  # cold brew
        self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)
        self.put_cold_cup()

    def make_cold_brew_with_milk(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.take_ingredients_cold_brew()  # cold brew
        self.take_ingredients_syrup()  # syrup
        self.take_ingredients_demo()  # milk
        self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)
        self.put_cold_cup()

    def make_cold_brew_foam_milk(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.take_ingredients_cold_brew()  # cold brew
        self.take_ingredients_demo()  # foam milk from treacle
        self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)
        self.put_cold_cup()

    def make_ice_americano(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.pass_cup("from_right")
        self.take_coffee_machine()  # amerciano
        self.put_hot_cup()

    def make_latte(self):
        self.take_hot_cup()

        def right_action():
            self.take_foam_cup()
            self.make_foam_demo()

        def left_action():
            self.take_coffee_machine_hot_milk()  # hot milk
            self.take_coffee_machine_demo_make()  # espresso
            self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)

        # self.take_coffee_machine_demo()#hot milk
        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()
        # self.take_coffee_machine()#hot milk
        # self.take_coffee_machine()#espresso
        # self.take_foam_cup()
        # self.make_foam()
        self.pour("ice")
        self.put_hot_cup()
        self.clean_foamer()
        self.put_foam_cup()

    def make_espresso(self):
        self.take_hot_cup()
        self.take_coffee_machine_demo_make()  # espresso
        self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)
        self.put_hot_cup()

    def make_daily_coffee(self):
        self.take_hot_cup()
        self.take_daily_coffee()

        # hot coffee from tank
        # self.take_coffee_machine()#espresso

        self.put_hot_cup()

    def make_hot_milk(self):
        self.take_hot_cup()
        self.take_coffee_machine_hot_milk()  # hot milk
        self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)
        self.put_hot_cup()

    def make_chocolate_milk(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.take_ingredients_demo()  # cold  milk
        self.take_ingredients_chocolate()  # chocalate or vanilla
        self.goto_initial_position_direction(Arm.right, 0, wait=True, speed=300)
        self.put_cold_cup()

    def make_hot_water(self):
        self.take_hot_cup()
        self.take_coffee_machine_hot_water()  # hot water
        self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)
        self.put_hot_cup()

    def make_cappucino(self):
        self.take_hot_cup()

        def right_action():
            self.take_foam_cup()
            self.make_foam_demo()

        def left_action():
            self.take_coffee_machine_espresso()  # espresso
            self.goto_temp_point(Arm.left, x=65, wait=False, speed=200)

        # self.take_coffee_machine_demo()#hot milk
        thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()
        # self.take_coffee_machine()#espresso
        # self.take_foam_cup()
        # self.make_foam()
        self.pour("ice")
        self.put_hot_cup()
        self.clean_foamer()
        self.put_foam_cup()

    def make_cold_americano(self):
        self.take_cold_cup()
        self.take_ice(1)
        self.pass_cup("from_right")
        self.take_americano()

        # hot coffee from tank
        # self.take_coffee_machine()#espresso
        self.put_hot_cup()

    def make_cold_drink_old(self, formula, sweetness, milk, ice, receipt_number):
        logger.debug('start in make_cold_drink')
        composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk, ice)

        put_cup_flag = Arm.right  # 放杯标志，由此判断是左手放杯还是右手放杯
        sent_flag = False  # 咖啡机指令发送标志

        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()

        self.left_record.proceed()
        self.right_record.proceed()  # 记录关节位置线程开启

        # step 1 换手前右手动作
        self.take_cold_cup()
        ice_level = composition.get(define.Constant.MachineType.ice_maker, {}).get('ice', 1)
        self.dip(composition.get(define.Constant.MachineType.power_box, {}))  # 有糖粉盒就蘸糖粉
        self.take_ice(ice_level)
        self.take_ingredients(Arm.right, composition.get(define.Constant.MachineType.tap, {}))  # 有调料就接调料

        # step 2 需要从咖啡机或者保温桶接饮料，说明要换手
        if composition.get(define.Constant.MachineType.coffee_machine, {}) or composition.get(
                define.Constant.MachineType.bucket, {}):
            coffee_config = composition.get(define.Constant.MachineType.coffee_machine, {})
            if coffee_config:
                coffee_dict = list(coffee_config.values())[0].get('coffee_make')
                try:
                    coffee_status = self.coffee_driver.query_status()
                    if coffee_status.get('system_status') == CoffeeMachineStatus.idle:
                        self.coffee_driver.make_coffee_from_dict(coffee_dict)
                        sent_flag = True
                    self.pass_cup('from_right')
                    put_cup_flag = Arm.left
                except Exception as e:
                    logger.error('some error in make_coffee_from_dict, err={}'.format(str(e)))
                    if COFFEE_STATUS.get('error_msg', {}).get('11') in str(e):
                        CoffeeInterface.bean_out()
                    self.stop()

        # step3
        def left_step3():
            self.take_coffee_machine(composition.get(define.Constant.MachineType.coffee_machine, {}), sent_flag)  # 有咖啡机就去咖啡机制作
            self.take_from_bucket(composition.get(define.Constant.MachineType.bucket, {}))  # 有保温桶就去接保温桶

        def right_step3():
            if composition.get(define.Constant.MachineType.foam_machine):
                self.take_foam_cup()
                self.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}))  # 有奶泡机就制作奶泡

        step3_thread = [threading.Thread(target=left_step3), threading.Thread(target=right_step3)]
        for t in step3_thread:
            t.start()
        for t in step3_thread:
            t.join()
        self.check_adam_status('make_cold_drink step3')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常

        # step 4
        if composition.get(define.Constant.MachineType.foam_machine, {}):
            # 有制作奶泡，需要将奶泡倒入杯中
            self.pour('ice')

        # 放杯子之前开始语音播报
        AudioInterface.gtts("receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))

        # step 5
        def left_step5():
            if put_cup_flag == Arm.left:
                self.put_hot_cup(cup='cold_cup')

        def right_step5():
            if put_cup_flag == Arm.right:
                self.put_cold_cup()
            elif composition.get(define.Constant.MachineType.foam_machine, {}):
                # 有制作奶泡，需要清洗
                time.sleep(2)  # 等待2秒钟，等左手离开洗杯区域，防止洗杯时碰撞
                self.clean_foamer()
                self.put_foam_cup()

        step5_thread = [threading.Thread(target=left_step5), threading.Thread(target=right_step5)]
        for t in step5_thread:
            t.start()
        for t in step5_thread:
            t.join()

        self.check_adam_status('make_cold_drink step5')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
        self.arduino.arduino.send_one_msg('0')  # 线程结束关闭所有arduino
        self.left_record.pause()
        self.right_record.pause()

    def _goto_work_zero_use_set_position_with_true(self):
        left_p = self.initial_position(Arm.left).dict()
        right_p = self.initial_position(Arm.right).dict()
        left_p.update({'wait': True, 'speed': 300})
        right_p.update({'wait': True, 'speed': 300})
        lcode, rcode = self.env.adam.set_position(left_p, right_p)
        if lcode != 0 or rcode != 0:  # move has error, stop adam
            self.stop()
            # self.roll()

    def get_composition_by_option(self, formula, cup, sweetness=0, milk=define.MilkType.milk, ice='no_ice') -> dict:
        """
        根据饮品名称查询配方表，返回不同机器处需要的物料名称和数量。同时根据选项对糖量等进行微调
        return:{
                'coffee_machine': {'coffee': {'count':60, 'coffee_make':{...}}}, # 用咖啡机的
                'bucket': {'americano': 320}, # 用保温桶的
                'power_box': {'sugar_power': 1}, # 要蘸糖粉的
                'foam_machine': {"foam": {"foam_composition": {"fresh_dairy":450 }, "foam_time":45} },# 奶泡
                'tap': {sugar':10, 'white_chocolate_syrup': 20, 'cold_coffee': 150}, # 用龙头的
                'ice_machine': {'ice': 0}, # 用制冰机的
                'cup': {'hot_cup': 1}
                }
        """
        composition = CoffeeInterface.get_formula_composition(formula, cup, define.Constant.InUse.in_use)
        if not composition:
            # 校验方案是否支持
            msg = 'there are no formula named {} in use, please check again'.format(formula)
            AudioInterface.gtts(msg)
            logger.error(msg)
            raise FormulaError(msg)
        result = {}
        lack = ''
        for name, material in composition.items():
            if material.get('in_use') == define.Constant.InUse.not_in_use:
                # 校验材料是否支持
                msg = 'material {} is not in use, please check again'.format(name)
                AudioInterface.gtts(msg)
                logger.error(msg)
                raise MaterialError(msg)
            if material.get('left') < material.get('count'):
                # 校验材料是否充足
                lack += ' ' + name

            machine_name = material.get('machine')

            # 根据选项更新数量
            if name == define.TreacleType.sugar:
                # 根据甜度调整糖的用量
                result.setdefault(machine_name, {})[name] = material.get('count') * sweetness / 100
            if name == 'ice':
                # 根据选项更新冰的等待系数
                result.setdefault(machine_name, {})[name] = self.get_ice_percent(ice)
            elif name == define.MilkType.milk:
                # 鲜奶改植物奶
                milk_type = define.MilkType.plant_based if milk == define.MilkType.plant_based else define.MilkType.milk
                result.setdefault(machine_name, {})[milk_type] = material.get('count')
            elif machine_name == define.Constant.MachineType.coffee_machine:
                # 咖啡机类型的全部要增加咖啡机制作配方字典
                coffee_data = dict(count=material.get('count'), coffee_make=material.get('coffee_make'))
                result.setdefault(machine_name, {})[name] = coffee_data
            elif machine_name == define.Constant.MachineType.foam_machine:
                foam_data = dict(foam_composition=material.get('extra', {}).get('foam_composition', {}),
                                 foam_time=material.get('extra', {}).get('foam_time', 45))
                result.setdefault(machine_name, {})[name] = foam_data
            else:
                result.setdefault(machine_name, {})[name] = material.get('count')
        logger.debug('composition is {}'.format(result))
        if lack:
            AudioInterface.gtts('material {} not enough please add them first'.format(lack))
            raise MaterialError('material {} not enough please add them first'.format(lack))
        return result

    def get_cup_config(self, cup_name) -> total_schema.GetCupConfig:
        cup_config = deepcopy([i for i in self.env.machine_config.get if i.name == cup_name][0])
        return cup_config

    def get_ice_percent(self, ice):
        delay_percent = 1
        if ice == define.IceType.no_ice:
            delay_percent = self.machine_config.task_option.ice_type.no_ice
        elif ice == define.IceType.light:
            delay_percent = self.machine_config.task_option.ice_type.light
        if ice == define.IceType.more:
            delay_percent = self.machine_config.task_option.ice_type.more
        return delay_percent

    def get_initial_position(self):
        # 回到作揖状态下
        left_pre_angles = [148.5, 20, -46.3, -52.1, 74.7, -23.9]
        right_pre_angles = [-148.5, 20, -46.3, 52.1, 74.7, 23.9]
        # left_position = [355, 160, 700, 0, 30, -90]
        # right_position = [355, -160, 700, 0, 30, 90]
        left_position = [355, 100, 630, 0, 60, -90]
        right_position = [355, -100, 630, 0, 60, 90]
        left_angles = self.inverse(define.Arm.left, left_position, left_pre_angles)
        right_angles = self.inverse(define.Arm.right, right_position, right_pre_angles)
        return left_angles, right_angles

    def stop_and_goto_zero(self):
        """
        Adam软件急停并回工作状态的零点
        """
        if self.task_status in [AdamTaskStatus.stopped, AdamTaskStatus.rolling,
                                AdamTaskStatus.dead, AdamTaskStatus.warm]:
            return {'msg': 'not ok', 'status': self.task_status}
        elif self.task_status == AdamTaskStatus.making:
            logger.debug('adam is making now, return in stop_and_goto_zero')
            return {'msg': 'ok', 'status': self.task_status}
        elif self.task_status == AdamTaskStatus.idle:
            self.goto_work_zero(speed=30, open_gripper=False)
            logger.debug('adam is idle now, return in stop_and_goto_zero')
            return {'msg': 'ok', 'status': self.task_status}
        else:
            logger.debug('adam is dancing now, stop and goto zero')
            self.env.adam.set_state(dict(state=4), dict(state=4))
            self.task_status = AdamTaskStatus.making  # temp
            # 停止播放音乐
            AudioInterface.stop()
            logger.warning("adam stop and wait 2 seconds")
            time.sleep(2)
            self.left.motion_enable()
            self.left.clean_error()
            self.left.clean_warn()
            self.left.set_state(0)
            self.right.motion_enable()
            self.right.clean_error()
            self.right.clean_warn()
            self.right.set_state(0)

            self.goto_work_zero(speed=30)
            logger.warning("adam stop and goto zero finish")
            print(f"self.task_status: {self.task_status}")
            self.task_status = AdamTaskStatus.idle
            return {'msg': 'ok', 'status': self.task_status}

    def goto_work_zero(self, speed=50, open_gripper=True):
        """Adam 回工作状态下零点"""
        # 回到工作状态下的零点
        left_pre_angles = [209.35, -26.49, -63.1, -90, 89.35, 0.41]
        left_position = list(self.initial_position(define.Arm.left).dict().values())
        left_angles = self.inverse(define.Arm.left, left_position, left_pre_angles)
        right_pre_angles = [-209.35, -26.49, -63.1, 90, 89.35, -0.41]
        right_position = list(self.initial_position(define.Arm.right).dict().values())
        right_angles = self.inverse(define.Arm.right, right_position, right_pre_angles)

        # 右手抓着调酒壶就先倒掉并放回
        # if not self.gripper_is_open(Arm.right):  # 夹爪不是张开状态，先放回调酒壶
        #     self.clean_shaker()
        #     # todo 根据夹爪角度判断调酒壶是正的还是倒的
        #     self.put_shaker()
        # if not self.gripper_is_open(Arm.left):
        #     # todo 丢弃手上的杯子
        #     # self.drop()
        #     pass

        if open_gripper:
            self.goto_gripper_position(Arm.left, self.env.gripper_open_pos, wait=False)
            self.goto_gripper_position(Arm.right, self.env.gripper_open_pos, wait=False)
        if not self.task_status or self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling,
                                                            AdamTaskStatus.dead]:
            # first run, self.task_status is None
            lcode, rcode = self.env.adam.set_servo_angle(dict(angle=left_angles, speed=speed, wait=True),
                                                         dict(angle=right_angles, speed=speed, wait=True))
            if lcode != 0 or rcode != 0:
                # self.stop()
                raise MoveError('adam goto angle_left={} angle_right={} fail, code={},{}'.
                                format(left_angles, right_angles, lcode, rcode))
        assert utils.compare_value(self.left.angles[:6], left_angles, abs_tol=1), \
            "left goto work zero {} failed, current={}".format(left_angles, self.left.angles[:6])
        assert utils.compare_value(self.right.angles[:6], right_angles, abs_tol=1), \
            "right goto work zero {} failed, current={}".format(right_angles, self.right.angles[:6])

    def stop(self):
        """
        Adam软件急停, 关闭所有gpio。如果急停按钮一直闭合，则无法关闭gpio
        """
        if self.left.state == 4 or self.right.state == 4:
            time.sleep(1)  # wait to open emergency button
            self.env.adam.set_state(dict(state=0), dict(state=0))
        self.env.adam.motion_enable(left={'enable': True}, right={'enable': True})
        self.env.adam.clean_warn()
        self.env.adam.clean_error()
        self.arduino.arduino.send_one_msg('0')  # 关闭所有arduino
        adam_crud.init_tap()

        self.env.adam.set_state(dict(state=4), dict(state=4))
        self.change_adam_status(AdamTaskStatus.stopped)
        # 停止播放音乐
        AudioInterface.stop()
        AudioInterface.gtts(CoffeeInterface.choose_one_speech_text(define.AudioConstant.TextCode.fail))
        logger.warning("adam stop")

    def resume(self):
        self.left.motion_enable()
        self.left.clean_error()
        self.left.clean_warn()
        self.left.set_state()
        self.right.motion_enable()
        self.right.clean_error()
        self.right.clean_warn()
        self.right.set_state()
        # time.sleep(2)
        self.goto_work_zero(speed=30)
        return 'ok'

    def move_in_circle(self, which, pose1: adam_schema.Pose, pose2: adam_schema.Pose, percent, wait=True, speed=None, roll_flag=False):
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            code = arm.move_circle(self, pose1, pose2, percent, speed=None, mvacc=None, mvtime=None, is_radian=None, wait=False, timeout=None,
                                   **kwargs)
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_standby_pose(self):
        """
        回到作揖动作
        """
        # return initial position
        left_angles, right_angles = self.get_initial_position()
        logger.info(
            'left_angles={}, right_angles={} in goto_standby_pose with status={}'.format(left_angles, right_angles,
                                                                                         self.task_status))
        # self.take_conveyer.stop()
        # self.put_conveyer.stop()
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead]:
            logger.info('goto_standby_pose')
            # self.goto_gripper_position(Arm.left, self.env.gripper_open_pos, wait=False)
            # self.goto_gripper_position(Arm.right, self.env.gripper_open_pos, wait=False)
            self.goto_gripper_position(Arm.left, 10, wait=False)
            self.goto_gripper_position(Arm.right, 10, wait=False)
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=50, wait=True),
                                          dict(angle=right_angles, speed=50, wait=True))
            self.left_record.pause()
            self.right_record.pause()

    def goto_point(self, which, pose: adam_schema.Pose, wait=True, speed=None, radius=50, timeout=None, roll_flag=False):
        """
        运动到点，可以指定速度比例，否则以machine.yml中的默认速度来运动
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        # arm.set_mode(0)
        # arm.set_state(0)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto pose={} at {} speed, wait={}'.format(which, pose.dict(), speed, wait))
            code = arm.set_position(**pose.dict(), speed=speed, wait=wait, radius=radius, timeout=timeout)
            if code not in [0, 100]:
                logger.error('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
                self.stop()
                raise MoveError('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_XYZ_point(self, which, pose: adam_schema.Pose, wait=True, speed=None, roll_flag=False):
        """
        运动到点，只要xyz，三个参数可以指定速度比例，否则以machine.yml中的默认速度来运动

        only uses xyz coordinates
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        # arm.set_mode(0)
        # arm.set_state(0)
        pose_dict = {'x': pose.x, 'y': pose.y, 'z': pose.z}
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_XYZ_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50)
            if code != 0:
                logger.error('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop()
                # self.roll()
                raise MoveError('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_blockly_point(self, which, points, wait=True, speed=None,
                           mvacc=None, roll_flag=False):
        """
        一些中间位置，可以只传一个位置参数，而不需要传全部
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        # arm.set_mode(0)
        # arm.set_state(0)
        pose_list = []
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_temp_point pose={} at {} speed, wait={}'.format(which, points, speed, wait))
            code = arm.set_position(*points, speed=speed, wait=wait, radius=50, mvacc=mvacc)
            if code != 0:
                logger.error('{} arm goto_temp_point pose={} fail, code={}'.format(which, points, code))
                self.stop()
                # self.roll()
                raise MoveError('{} arm goto_temp_point pose={} fail, code={}'.format(which, points, code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_temp_point(self, which, x=None, y=None, z=None, roll=None, pitch=None, yaw=None, wait=True, speed=None,
                        mvacc=None, roll_flag=False):
        """
        一些中间位置，可以只传一个位置参数，而不需要传全部
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        # arm.set_mode(0)
        # arm.set_state(0)
        pose_dict = {'x': x, 'y': y, 'z': z, 'roll': roll, 'pitch': pitch, 'yaw': yaw}
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_temp_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50, mvacc=mvacc)
            if code != 0:
                logger.error('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop()
                # self.roll()
                raise MoveError('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_gripper_position(self, which, pos, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            arm.set_gripper_enable(True)
            arm.set_gripper_mode(0)
            arm.set_gripper_position(pos, wait=wait, speed=self.env.default_gripper_speed)

    def goto_tool_position(self, which, x=0, y=0, z=0, roll=0, pitch=0, yaw=0,
                           speed=None, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            code = arm.set_tool_position(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=speed, wait=wait)
            if code != 0:
                logger.error('{} arm goto_tool_position fail, code={}'.format(which, code))
                self.stop()
                # self.roll()
                raise MoveError('{} arm goto_tool_position fail, code={}'.format(which, code))

    def goto_angles(self, which, angles: adam_schema.Angles, wait=True, speed=50, roll_flag=False):
        angle_list = list(dict(angles).values())
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.info('{} arm set_servo_angle from {} to {}'.format(which, arm.angles[:6], angle_list))
            return_code = arm.set_servo_angle(angle=angle_list, speed=speed, wait=wait)
            now_angles = arm.angles
            if return_code != 0:
                self.stop()
                # self.roll()
                raise MoveError('{} arm goto angle={} fail, code={}'.format(which, angle_list, return_code))
            return now_angles

    def safe_set_state(self, which, state=0):
        arm = self.env.one_arm(which)
        if arm.state != 4:
            self.env.one_arm(which).set_state(state)

    def open_gpio(self, which, number, delay_time, roll_flag=False):
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('open gpio for {} seconds in open_gpio'.format(delay_time))
            self.env.one_arm(which).set_cgpio_digital(number, 1)
            # AudioInterface.tts('open gpio now', False)
            time.sleep(delay_time)
            # AudioInterface.tts('close gpio now', False)
            self.env.one_arm(which).set_cgpio_digital(number, 0)
            logger.debug('close gpio and wait for 2s in open_gpio')
            time.sleep(2)
            logger.debug('after wait 2s in open_gpio')
            logger.info('open {} gpio={} for {} seconds ends'.format(which, number, delay_time))

    def check_adam_goto_initial_position(self):
        # 检测adam是否回到零点，若有报错，adam服务直接退出
        try:
            logger.info('adam goto initial position before work')
            os.system('chmod +x /richtech/resource/adam/kinematics/*')
            self.goto_work_zero(speed=50)
            self.goto_gripper_position(Arm.left, 0, wait=False)
            self.goto_gripper_position(Arm.right, 0, wait=False)
            left_angles, right_angles = self.get_initial_position()
            logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=50, wait=True),
                                          dict(angle=right_angles, speed=50, wait=True))
            assert utils.compare_value(self.left.angles[:6], left_angles, abs_tol=1), \
                "left goto initial {} failed, current={}".format(left_angles, self.left.angles[:6])
            assert utils.compare_value(self.right.angles[:6], right_angles, abs_tol=1), \
                "right goto initial {} failed, current={}".format(right_angles, self.right.angles[:6])
            ExceptionInterface.clear_error(ExceptionType.adam_initial_position_failed)
        except Exception as e:
            ExceptionInterface.add_error(ExceptionType.adam_initial_position_failed, str(e))
            logger.error(traceback.format_exc())
            logger.error('{}, err={}'.format(ExceptionType.adam_initial_position_failed, str(e)))
            self.env.adam.motion_enable(left={'enable': True}, right={'enable': True})
            self.env.adam.clean_warn()
            self.env.adam.clean_error()
            time.sleep(1)
            self.env.adam.set_mode(dict(mode=2), dict(mode=2))
            time.sleep(0.5)
            self.env.adam.set_state(dict(state=0), dict(state=0))
            logger.warning("open teach mode")
            time.sleep(9.5)
            exit(-1)

    def check_adam_status(self, desc):
        logger.info('check after {}, status is {}'.format(desc, self.task_status))
        if self.task_status in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead]:
            raise MoveError('move error in {}'.format(desc))

    def inverse(self, which, pose_list: list, q_pre_list: list = None):
        pose_list = [str(i) for i in pose_list]
        q_pre_list = [str(i) for i in q_pre_list or [0] * 6]
        tcp_list = [str(i) for i in self.env.get_tcp_offset(which).dict().values()]
        world_list = [str(i) for i in self.env.get_world_offset(which).dict().values()]
        param_str = "{} {} {} {}".format(
            ' '.join(pose_list), ' '.join(tcp_list), ' '.join(world_list), ' '.join(q_pre_list))
        cmd = '{}/ik {} '.format(define.BIN_PATH, param_str)
        ret = utils.get_execute_cmd_result(cmd)
        logger.debug('inverse {} input: pose={}, q_pre={}, result: {}'.format(which, pose_list, q_pre_list, ret))
        angle_list = ret.strip().split(' ')
        logger.info('cmd={}, ret={}'.format(cmd, angle_list))
        return [round(float(i), 2) for i in angle_list]

    def current_position(self, which) -> adam_schema.Pose:
        arm = self.env.one_arm(which)
        value = dict(zip(define.POSITION_PARAM, arm.position))
        logger.debug('{} arm current pose={}'.format(which, value))
        return adam_schema.Pose(**value)

    def current_angles(self, which) -> adam_schema.Angles:
        arm = self.env.one_arm(which)
        value = dict(zip(define.ANGLE_PARAM, arm.angles))
        logger.debug('{} arm current pose={}'.format(which, value))
        return adam_schema.Angles(**value)

    def gripper_is_open(self, which):
        arm = self.env.one_arm(which)
        code, pos = arm.get_gripper_position()
        if code == 0:
            if abs(pos - self.env.gripper_open_pos) <= 10:
                return True
            else:
                return False
        else:
            logger.error('{} arm gripper out of control with code {}'.format(which, code))
            raise Exception('{} arm gripper out of control with code {}'.format(which, code))

    def change_adam_status(self, status):
        """
        只有在跳舞的时候，切换为制作状态，才会触发强制停止并回工作零点
        """
        if status == AdamTaskStatus.making and self.task_status == AdamTaskStatus.dancing:
            self.stop_and_goto_zero()
            self.task_status = AdamTaskStatus.making
        elif self.task_status == AdamTaskStatus.rolling:
            # if adam is rolling, can not change status by this function, need to change status in roll thread
            pass
        else:
            self.task_status = status

    def get_xy_initial_angle(self, which, x, y) -> float:
        src = self.initial_center_point(which)
        x0, y0 = src['x'], src['y']
        return math.atan2(y0 - y, x - x0) / math.pi * 180

    def initial_center_point(self, which):
        y = common_schema.AdamArm.initial_y
        y = abs(y) if which == Arm.left else -abs(y)
        z = 250
        return {'x': 0, 'y': y, 'z': z}

    def center_to_tcp_length(self, which):
        # 工作零点的x坐标如何计算
        gripper_name = getattr(self.env.adam_config.different_config, which).gripper
        return self.env.adam_config.gripper_config[gripper_name].tcp_offset.z + common_schema.AdamArm.line6

    def initial_position(self, which) -> adam_schema.Pose:
        # 计算工作零点的位姿
        center_position = self.initial_center_point(which)
        center_position['x'] = self.center_to_tcp_length(which)
        center_position.update(dict(roll=0, pitch=90, yaw=0))
        return adam_schema.Pose(**center_position)

    def initial_position_direction(self, which, angle):
        """
        自定义initial_position为默认的工作零点，angle表示在中转点转动一个角度
        机械臂在中转点附近有很大的工作空间
        """
        center_position = self.initial_center_point(which)  # [0, +-550, 250]
        line = self.center_to_tcp_length(which)
        x = round(line * math.cos(-math.radians(angle)) + center_position['x'], 2)
        y = round(line * math.sin(-math.radians(angle)) + center_position['y'], 2)
        position = {'x': x, 'y': y, 'z': center_position['z'], 'roll': angle, 'pitch': 90, 'yaw': 0}
        logger.debug('{} arm initial angle={} position={}'.format(which, angle, position))
        return adam_schema.Pose(**position)

    def goto_initial_position_direction(self, which, angle, wait=True, speed=600):
        pose = self.initial_position_direction(which, angle)
        return self.goto_point(which, pose, wait=wait, speed=speed)

    def warm_up(self):
        warm_speed = 20
        left_init_angle = [132.3, 8.7, -34.5, -45.9, 42.8, -38.7]
        right_init_angle = [-132, 8.7, -34.5, 45.9, 42.8, 38.7]
        left_heart_angle = [30, 29, -59, 0, 60, 0, 0]
        right_heart_angle = [-30, 28, -59, 0, 60, 180, 0]
        if self.task_status != AdamTaskStatus.idle:
            return 'not ok, now is {}'.format(self.task_status)
        else:
            self.change_adam_status(AdamTaskStatus.warm)
        try:
            # 全是相对运动，第一步位置必须固定
            self.left.set_servo_angle(angle=left_init_angle, speed=warm_speed, wait=False)
            self.right.set_servo_angle(angle=right_init_angle, speed=warm_speed, wait=True)

            self.left.set_servo_angle(angle=[-180, 0, 0, 0, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.right.set_servo_angle(angle=[180, 0, 0, 0, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[90, 0, 0, 0, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.right.set_servo_angle(angle=[-90, 0, 0, 0, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, -90, 30, -135, 0, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, -81.3, -4.5, -180.9, 42.8, -38.7]
            self.right.set_servo_angle(angle=[0, -90, 30, 135, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, 30, -30, 135, -60, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, -51.3, -34.5, -45.9, -17.2, -38.7]
            self.right.set_servo_angle(angle=[0, 30, -30, -135, -60, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.right.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.left.set_servo_angle(angle=[0, 0, -40, 200, 0, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, -21.3, -74.5, 154.1, -17.2, -38.7]
            self.right.set_servo_angle(angle=[0, 0, -40, -200, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.right.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.left.set_servo_angle(angle=[0, 0, -30, -100, 0, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, 8.7, -74.5, 54.1, -17.2, -38.7]
            self.right.set_servo_angle(angle=[0, 0, -30, 100, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.right.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.left.set_servo_angle(angle=[0, 0, -30, -100, 0, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, 38.6, -134.5, -45.9, -17.7, -38.7]
            self.right.set_servo_angle(angle=[0, 0, -30, 100, 0, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.right.set_servo_angle(angle=[0, 30, 0, 0, 0, 0], relative=True, speed=int(warm_speed / 2), wait=False)
            self.left.set_servo_angle(angle=[0, 0, -50, 0, 45, 0], relative=True, speed=warm_speed,
                                      wait=False)  # -> [42.3, 68.6, -184.5, -45.9, 27.3, -38.7]
            self.right.set_servo_angle(angle=[0, 0, -50, 0, 45, 0], relative=True, speed=warm_speed, wait=False)
            self.left.set_servo_angle(angle=left_heart_angle, speed=warm_speed, wait=False)
            self.right.set_servo_angle(angle=right_heart_angle, speed=warm_speed + 5, wait=False)
            self.left.set_servo_angle(angle=left_init_angle, speed=warm_speed, wait=False)
            self.right.set_servo_angle(angle=right_init_angle, speed=warm_speed + 5, wait=True)
        finally:
            self.change_adam_status(AdamTaskStatus.idle)
            return 'ok'

    def back(self, which, file_path):
        """
        rollback according to the records in file
        """
        logger.info('before {} record thread rollback'.format(which))
        # time.sleep(20)  # waiting for the main thread to release control of the arm
        arm = self.env.one_arm(which)
        arm.motion_enable(enable=True)
        arm.set_mode(0)
        arm.set_state(state=0)
        arm.set_gripper_enable(True)
        arm.set_gripper_mode(0)
        arm.set_gripper_position(self.env.gripper_open_pos, wait=True)  # open gripper first
        logger.info('{} record thread rolling back'.format(which))
        if not os.path.exists(file_path):
            return 0, 'do not neet to end after roll back'

        with open(file_path) as f:
            p_csv = csv.reader(f)
            pos = list(p_csv)
            for i in range(len(pos)):
                pos[i] = list(map(float, pos[i]))

        count = len(pos)
        # if count <= 3:
        #     return 0, 'do not neet to end after roll back'
        logger.debug('start rolling')
        while arm.connected and arm.state != 4:
            if count == 1 or count % 10 == 0:
                logger.debug('the last rolling')
                code = arm.set_servo_angle(angle=pos[count - 1], radius=2, wait=True, speed=20)
                if code != 0:
                    return 2, 'roll back error'
            else:
                code = arm.set_servo_angle(angle=pos[count - 1], radius=2, wait=False, speed=20)
                if code != 0:
                    return 2, 'roll back error'
            count = count - 1
            if count == 0:
                self.goto_initial_position_direction(which, 0, wait=True, speed=20)  # 回零点
                break
        else:
            # self.task_status = AdamTaskStatus.dead
            return 2, 'state is 4, do not change adam status'
        logger.info('{} record thread rollback complete'.format(which))
        return 1, 'need to end after roll'  # not use now

    def roll(self):
        logger.warning('adam prepare to roll back')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.dead]:
            return 'don\'t need to roll back'
        self.change_adam_status(AdamTaskStatus.rolling)
        time.sleep(5)  # wait for someone to be ready to take the cup and shaker
        self.left_roll_end = False
        self.right_roll_end = False

        def roll_end():
            logger.debug('try to roll end with left_roll_end={}, right_roll_end={}'.format(self.left_roll_end,
                                                                                           self.right_roll_end))
            if self.left_roll_end and self.right_roll_end:
                logger.debug('real roll end, change Adam status to idle')
                self.task_status = AdamTaskStatus.idle
                AudioInterface.gtts('/richtech/resource/audio/voices/ready.mp3')

        # def dead():
        #     self.task_status = AdamTaskStatus.dead
        #     self.env.adam.set_state(dict(state=4), dict(state=4))
        #     time.sleep(5)
        #     logger.debug('wait after 5s, before manual in dead')
        #     if self.left.state == 4 or self.right.state == 4:
        #         self.env.adam.set_state(dict(state=0), dict(state=0))
        #         default_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
        #         default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
        #         default_tool_gravity = list(
        #             self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
        #         self.env.adam.set_tcp_offset(dict(offset=default_offset), dict(offset=default_offset))
        #         self.left.set_tcp_offset(offset=default_offset)  # 恢复默认夹爪偏移
        #         self.left.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)  # 恢复默认设置夹爪载重
        #         self.safe_set_state(Arm.left, 0)
        #         logger.debug('set both state to 0 in dead')
        #     self.env.adam.motion_enable(left={'enable': True}, right={'enable': True})
        #     self.env.adam.clean_warn()
        #     self.env.adam.clean_error()
        #     self.env.adam.set_mode(dict(mode=2), dict(mode=2))
        #     self.env.adam.set_state(dict(state=0), dict(state=0))
        #     for i in range(3):
        #         # try to open manual mode for another 3 times
        #         # if self.left.mode != 2 or self.right.mode != 2:
        #         logger.debug('start try open manual mode for {} time in dead'.format(i))
        #         self.env.adam.set_state(dict(state=0), dict(state=0))
        #         self.env.adam.motion_enable(left={'enable': True}, right={'enable': True})
        #         self.env.adam.clean_warn()
        #         self.env.adam.clean_error()
        #         self.env.adam.set_mode(dict(mode=2), dict(mode=2))
        #         self.env.adam.set_state(dict(state=0), dict(state=0))
        #         logger.debug('end try open manual mode for {} time in dead'.format(i))
        #         time.sleep(1)
        #         # break
        #     if self.left.mode != 2 or self.right.mode != 2:
        #         AudioInterface.tts('failed to open manual mode')
        #         logger.warning('failed to open manual mode')
        #     else:
        #         AudioInterface.tts('open manual mode successfully')
        #         logger.info('open manual mode successfully')

        def dead(which):
            self.task_status = AdamTaskStatus.dead
            arm = self.env.one_arm(which)
            time.sleep(5)
            logger.debug('wait after 5s, before manual in dead')
            if arm.state == 4:
                arm.set_state(state=0)
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
            arm.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)  # 恢复默认设置夹爪载重
            arm.motion_enable(enable=True)
            arm.clean_warn()
            arm.clean_error()
            arm.set_mode(mode=2)
            arm.set_state(state=0)
            for i in range(3):
                # try to open manual mode for another 3 times
                # if self.left.mode != 2 or self.right.mode != 2:
                logger.debug('start try open manual mode for {} time in dead'.format(i))
                arm.set_state(state=0)
                arm.motion_enable(enable=True)
                arm.clean_warn()
                arm.clean_error()
                arm.set_mode(mode=2)
                arm.set_state(state=0)
                logger.debug('end try open manual mode for {} time in dead'.format(i))
                time.sleep(1)
                # break
            if self.left.mode != 2 or self.right.mode != 2:
                AudioInterface.gtts(define.AudioConstant.get_mp3_file(define.AudioConstant.TextCode.manual_failed))
                # AudioInterface.gtts('failed to open manual mode')
                logger.warning('failed to open manual mode')
            else:
                AudioInterface.gtts(define.AudioConstant.get_mp3_file(define.AudioConstant.TextCode.manual_succeed))
                # AudioInterface.gtts('open manual mode successfully')
                logger.info('open manual mode successfully')

        def left_roll():
            lflag, msg = self.back(Arm.left, self.env.get_record_path(Arm.left))
            logger.debug('left back flag = {}, {}'.format(lflag, msg))
            if lflag == 0:
                self.left_roll_end = True
                roll_end()
            elif lflag == 1:
                # self.clean_shaker(roll_flag=True)
                self.left_roll_end = True
                roll_end()
            else:
                # lflag=2, rollback error
                logger.warning('left roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                dead(Arm.left)
            logger.warning('adam left arm roll back end')

        def right_roll():
            rflag, msg = self.back(Arm.right, self.env.get_record_path(Arm.right))
            logger.debug('right back flag = {}, {}'.format(rflag, msg))
            if rflag == 0:
                self.right_roll_end = True
                roll_end()
            elif rflag == 1:
                # self.put_cup(roll_flag=True)
                self.right_roll_end = True
                roll_end()
            else:
                # rflag=2
                logger.warning('right roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                dead(Arm.right)
            logger.warning('adam right arm roll back end')

        thread_list = [
            threading.Thread(target=left_roll),
            threading.Thread(target=right_roll)
        ]
        for t in thread_list:
            t.start()

    def manual(self, which, mode=2):
        arm = self.env.one_arm(which)
        arm.set_state(state=0)
        arm.motion_enable(enable=True)
        arm.clean_warn()
        arm.clean_error()
        arm.set_mode(mode=mode)
        arm.set_state(state=0)
        return arm.mode

    def init_adam(self):
        self.env.init_adam()

    def dance_in_thread(self):
        def dance():
            default_speed = 600
            start_time = time.perf_counter()
            self.check_adam_goto_initial_position()
            AudioInterface.music('dance.mp3')

            def get_position_value(position, **kwargs):
                v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
                value = dict(zip(v, position))
                kwargs.setdefault('speed', 1000)
                kwargs.setdefault('mvacc', 1000)
                return dict(value, **kwargs)

            def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
                left_speed = left_speed or default_speed
                right_speed = right_speed or default_speed
                left = get_position_value(data[Arm.left][point_name]['position'],
                                          wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
                right = get_position_value(data[Arm.right][point_name]['position'],
                                           wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
                self.env.adam.set_position(left, right)

            def get_next_point_speed(point_name):
                left_p, right_p = self.env.adam.position
                [x1, y1, z1] = left_p[:3]
                [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
                left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                [x1, y1, z1] = right_p[:3]
                [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
                right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if left_d > right_d:
                    s = int(left_d / right_d * default_speed)
                    return default_speed, s
                else:
                    s = int(left_d / right_d * default_speed)
                    return s, default_speed

            data = utils.read_resource_json('/adam/data/dance.json')
            # 回到舞蹈初始点
            set_adam_position('zero')
            # hello
            self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position'], wait=True))
            # hello 2次
            for i in range(2):
                self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello2']['position']))
                self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position']))

            # 回到舞蹈初始点
            set_adam_position('zero', wait=True)
            # 同时运动到挥手位置
            left_speed, right_speed = get_next_point_speed('huang-you')
            set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
            # 左右挥手
            start_hui_time = time.perf_counter()
            for i in range(6):
                set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
            set_adam_position('huang-you', wait=True)
            logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
            # 挥手后回到初始位置
            left_speed, right_speed = get_next_point_speed('zero')
            set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)
            # 切菜
            set_adam_position('qian_shen', wait=True)
            fu_du = 50
            for i in range(8):
                left_position = deepcopy(data[Arm.left]['qie-cai']['position'])
                right_position = deepcopy(data[Arm.right]['qie-cai']['position'])
                if i % 2 == 0:
                    left_position[2] += fu_du
                    right_position[2] -= fu_du
                else:
                    left_position[2] -= fu_du
                    right_position[2] += fu_du
                y_pian = [0, -50, -100, -50, 0, 50, 100, 50]
                left_position[1] += y_pian[i]
                right_position[1] += y_pian[i]
                left = get_position_value(left_position, radius=50)
                right = get_position_value(right_position, radius=50)
                self.env.adam.set_position(left, right)
            # zero
            set_adam_position('zero', wait=True)
            # 画圆
            # self.set_adam_circle('circle0', 'circle1', 100, start_point='zero', circle_speed=500)
            # 比爱心
            set_adam_position('ai-zhong', left_speed=400, right_speed=400)
            set_adam_position('ai', left_speed=400, right_speed=400)
            # 爱心左右移动
            for i in range(2):
                set_adam_position('ai-left')
                set_adam_position('ai-right')
            # 回到标准爱心位置
            set_adam_position('ai')
            # 回到舞蹈初始点
            set_adam_position('ai-zhong', left_speed=400, right_speed=400)
            set_adam_position('zero', left_speed=400, right_speed=400, wait=True)
            set_adam_position('prepare', wait=True)
            logger.info('dance use_time={}'.format(time.perf_counter() - start_time))

        def run_dance():
            try:
                self.task_status = AdamTaskStatus.dancing
                self.env.adam.set_tcp_offset(dict(offset=[0] * 6), dict(offset=[0] * 6))
                self.env.adam.set_state(dict(state=0), dict(state=0))
                dance()
            except Exception as e:
                logger.error('dance have a error is {}'.format(str(e)))
                logger.error(traceback.format_exc())
            finally:
                AudioInterface.stop()
                self.env.init_adam()
                self.task_status = AdamTaskStatus.idle

        if self.task_status != AdamTaskStatus.idle:
            return self.task_status
        self.task_status = AdamTaskStatus.dancing
        t = threading.Thread(target=run_dance)
        t.setDaemon(True)
        t.start()
        return self.task_status

    def dance1_in_thread(self):
        def dance():
            self.check_adam_goto_initial_position()

            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position()

            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(x=156.8, y=708, z=1256, roll=1.7, pitch=11.9, yaw=-9.7, speed=550, wait=True)
                for i in range(3):
                    self.left.set_servo_angle(servo_id=4, angle=-50, speed=80, wait=False)
                    self.left.set_servo_angle(servo_id=4, angle=-150, speed=80, wait=False)
                self.left.set_servo_angle(servo_id=4, angle=-115, speed=80, wait=True)
                self.left.set_servo_angle(angle=[141.3, 17.2, -41.7, -58.5, 71.1, -24.1], speed=50, wait=True)  # 抱胸

            for i in range(6):  # run
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 205, 'y': 550, 'z': 250, 'roll': -110, 'pitch': 0, 'yaw': -90, 'speed': 700},
                        right={'x': 405, 'y': -550, 'z': 350, 'roll': 70, 'pitch': 0, 'yaw': 90, 'speed': 700}
                    )
                    self.env.adam.set_position(
                        left={'x': 405, 'y': 550, 'z': 350, 'roll': -70, 'pitch': 0, 'yaw': -90, 'speed': 700},
                        right={'x': 205, 'y': -550, 'z': 250, 'roll': 110, 'pitch': 0, 'yaw': 90, 'speed': 700}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 305, 'y': 550, 'z': 250, 'roll': -90, 'pitch': 0, 'yaw': -90, 'speed': 250,
                          'wait': True},
                    right={'x': 305, 'y': -550, 'z': 250, 'roll': 90, 'pitch': 0, 'yaw': 90, 'speed': 250, 'wait': True}
                )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 400, 'wait': True},
                    right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 600, 'wait': True}
                )
            for i in range(2):  # clap
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 500, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                        right={'x': 500, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250}
                    )
                    self.env.adam.set_position(
                        left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                        right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 580, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 500, 'wait': True},
                    right={'x': 580, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 500, 'wait': True}
                )
            for i in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.move_circle(
                        left={'pose1': [580, 200, 900, 0, 0, 0], 'pose2': [580, 0, 900, 0, 0, 0], 'percent': 100,
                              'speed': 200, 'wait': False},
                        right={'pose1': [580, -0, 900, 0, 0, 180], 'pose2': [580, -200, 900, 0, 0, 180], 'percent': 100,
                               'speed': 200, 'wait': False}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 580, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': True},
                    right={'x': 580, 'y': -200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},
                    right={'angle': [-38.5, -27.7, -64.8, 176.7, 89.1, 11.8], 'speed': 50, 'wait': True}
                )
                for i in range(2):
                    self.right.set_servo_angle(angle=[-43.1, -26.5, -94.9, 177.7, 57.1, 12.1], speed=50, wait=False,
                                               radius=20)
                    self.right.set_servo_angle(angle=[-38.5, -27.7, -64.8, 176.7, 89.1, 11.8], speed=50, wait=False,
                                               radius=20)
                self.env.adam.set_servo_angle(
                    left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},
                    right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
                )
                self.env.adam.set_servo_angle(
                    left={'angle': [26.3, -24.9, -64.8, -184, 85.7, 9.4], 'speed': 50, 'wait': True},
                    right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
                )
                for i in range(2):
                    self.left.set_servo_angle(angle=[26.5, -22.2, -94.1, -190, 63.5, 10.4], speed=50, wait=False,
                                              radius=20)
                    self.left.set_servo_angle(angle=[26.3, -24.9, -64.8, -184, 85.7, 9.4], speed=50, wait=False,
                                              radius=20)

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},  # init
                    right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 450, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True}
                )

            for i in range(4):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
                    self.env.adam.set_position(
                        left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 20, 'wait': True},
                    right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 27, 'wait': True},
                )

        def run_dance():
            try:
                self.task_status = AdamTaskStatus.dancing
                dance_times = self.env.machine_config.dance.count
                AudioInterface.stop()
                AudioInterface.gtts(
                    CoffeeInterface.choose_one_speech_text(define.AudioConstant.TextCode.start_dancing), True)
                AudioInterface.music('ymca.mp3', delay=2)
                for i in range(dance_times):
                    logger.info('the {}/{} times dance'.format(i + 1, dance_times))
                    dance()
            except Exception as e:
                logger.error('dance1 have a error is {}'.format(str(e)))
                logger.error(traceback.format_exc())
            finally:
                AudioInterface.stop()
                AudioInterface.gtts(
                    CoffeeInterface.choose_one_speech_text(define.AudioConstant.TextCode.end_dancing), True)
                self.env.init_adam()
                self.task_status = AdamTaskStatus.idle

        if self.task_status != AdamTaskStatus.idle:
            return self.task_status
        self.task_status = AdamTaskStatus.dancing
        t = threading.Thread(target=run_dance)
        t.setDaemon(True)
        t.start()
        return self.task_status

    def dance_random(self, choice):
        default_speed = 600

        def dance1():
            # hi
            AudioInterface.music('hi.mp3')

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800, wait=True)
                for i in range(4):
                    self.right.set_position(x=149, y=-402, z=1185, roll=27.7, pitch=-11.2, yaw=175, speed=800,
                                            wait=False)
                    self.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800,
                                            wait=False)
                self.right.set_servo_angle(angle=[-132.32, 8.69, -34.49, 45.93, 42.84, 38.71], speed=40, wait=True)

        def dance2():
            # heart
            AudioInterface.music('whistle.mp3')
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},  # init
                    right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 450, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True}
                )

            for i in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
                    self.env.adam.set_position(
                        left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
                )
                #
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 20, 'wait': True},
                    right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 27, 'wait': True},
                )

        def dance3():
            # cheer

            def get_position_value(position, **kwargs):
                v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
                value = dict(zip(v, position))
                kwargs.setdefault('speed', 1000)
                kwargs.setdefault('mvacc', 1000)
                return dict(value, **kwargs)

            def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
                left_speed = left_speed or default_speed
                right_speed = right_speed or default_speed
                left = get_position_value(data[Arm.left][point_name]['position'],
                                          wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
                right = get_position_value(data[Arm.right][point_name]['position'],
                                           wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
                self.env.adam.set_position(left, right)

            def get_next_point_speed(point_name):
                left_p, right_p = self.env.adam.position
                [x1, y1, z1] = left_p[:3]
                [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
                left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                [x1, y1, z1] = right_p[:3]
                [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
                right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if left_d > right_d:
                    s = int(left_d / right_d * default_speed)
                    return default_speed, s
                else:
                    s = int(left_d / right_d * default_speed)
                    return s, default_speed

            data = utils.read_resource_json('/adam/data/dance.json')
            AudioInterface.music('wa.mp3')
            set_adam_position('zero', wait=True)
            # 同时运动到挥手位置
            left_speed, right_speed = get_next_point_speed('huang-you')
            set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
            # 左右挥手
            start_hui_time = time.perf_counter()
            for i in range(3):
                set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
            set_adam_position('huang-you', wait=True)
            logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
            # 挥手后回到初始位置
            left_speed, right_speed = get_next_point_speed('zero')
            set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)

        def dance4():
            logger.info('dance4!!!')
            AudioInterface.music('YouNeverCanTell.mp3')
            for i in range(4):
                # 两者手臂左右晃动
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 310, 'y': -550, 'z': 250, 'roll': 11, 'pitch': 90, 'yaw': 11, 'speed': 400,
                               'wait': True},
                        left={'x': 310, 'y': 550, 'z': 250, 'roll': -11, 'pitch': 90, 'yaw': -11, 'speed': 400,
                              'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(  #
                            right={'x': 336, 'y': -187, 'z': 631, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                                   'wait': False},
                            left={'x': 336, 'y': 247, 'z': 521, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 336, 'y': -247, 'z': 521, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                                   'wait': False},
                            left={'x': 336, 'y': 187, 'z': 631, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                                  'wait': True}
                        )
                # 胸前两只手臂左右摇晃
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                               'wait': True},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                              'wait': True}
                    )

                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 395, 'y': 105, 'z': 763, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 400,
                              'wait': False},
                        right={'x': 395, 'y': -105, 'z': 763, 'roll': -0, 'pitch': 0, 'yaw': 90, 'speed': 400,
                               'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(  #
                            right={'x': 395, 'y': -300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': 90, 'speed': 400,
                                   'wait': False},
                            left={'x': 395, 'y': -10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': -90, 'speed': 400,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 395, 'y': 10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': 90, 'speed': 400,
                                   'wait': False},
                            left={'x': 395, 'y': 300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': -90, 'speed': 400,
                                  'wait': True}
                        )

                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                               'wait': False},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                              'wait': True}
                    )
                # 动作剪刀手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 395, 'y': 107, 'z': 429, 'roll': -70, 'pitch': 82, 'yaw': -154, 'speed': 400,
                                  'wait': False},
                            right={'x': 283, 'y': -107, 'z': 830, 'roll': 34, 'pitch': 10, 'yaw': 177, 'speed': 400,
                                   'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 395, 'y': -107, 'z': 429, 'roll': 70, 'pitch': 82, 'yaw': 154, 'speed': 400,
                                   'wait': False},
                            left={'x': 283, 'y': 107, 'z': 830, 'roll': -34, 'pitch': 0, 'yaw': -177, 'speed': 400,
                                  'wait': True}
                        )

        def dance5():
            logger.info('dance5!!!')

            self.task_status = AdamTaskStatus.dancing
            self.env.adam.set_tcp_offset(dict(offset=[0] * 6), dict(offset=[0] * 6))
            self.env.adam.set_state(dict(state=0), dict(state=0))
            default_speed = 600
            start_time = time.perf_counter()

            left_angles, right_angles = self.get_initial_position()
            logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                          dict(angle=right_angles, speed=20, wait=True))
            # self.check_adam_goto_initial_position()
            AudioInterface.music('dance.mp3')

            def get_position_value(position, **kwargs):
                v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
                value = dict(zip(v, position))
                kwargs.setdefault('speed', 1000)
                kwargs.setdefault('mvacc', 1000)
                return dict(value, **kwargs)

            def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
                left_speed = left_speed or default_speed
                right_speed = right_speed or default_speed
                left = get_position_value(data[Arm.left][point_name]['position'],
                                          wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
                right = get_position_value(data[Arm.right][point_name]['position'],
                                           wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
                self.env.adam.set_position(left, right)

            def get_next_point_speed(point_name):
                left_p, right_p = self.env.adam.position
                [x1, y1, z1] = left_p[:3]
                [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
                left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                [x1, y1, z1] = right_p[:3]
                [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
                right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if left_d > right_d:
                    s = int(left_d / right_d * default_speed)
                    return default_speed, s
                else:
                    s = int(left_d / right_d * default_speed)
                    return s, default_speed

            data = utils.read_resource_json('/adam/data/dance1.json')
            for i in range(3):  # 6
                if self.task_status == AdamTaskStatus.making:
                    break
                # 回到舞蹈初始点
                set_adam_position('zero')
                # hello
                self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position'], wait=True))
                # hello 2次
                for i in range(2):
                    self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello2']['position']))
                    self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position']))

                # # 回到舞蹈初始点
                set_adam_position('zero', wait=True)
                # # 同时运动到挥手位置
                left_speed, right_speed = get_next_point_speed('huang-you')
                set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
                # # 左右挥手
                start_hui_time = time.perf_counter()
                for i in range(6):
                    set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                    set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', wait=True)
                logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
                # 挥手后回到初始位置
                left_speed, right_speed = get_next_point_speed('zero')
                set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)
                # 切菜
                set_adam_position('qian_shen', wait=True)
                fu_du = 50
                for i in range(8):
                    left_position = deepcopy(data[Arm.left]['qie-cai']['position'])
                    right_position = deepcopy(data[Arm.right]['qie-cai']['position'])
                    if i % 2 == 0:
                        left_position[2] += fu_du
                        right_position[2] -= fu_du
                    else:
                        left_position[2] -= fu_du
                        right_position[2] += fu_du
                    y_pian = [0, -50, -100, -50, 0, 50, 100, 50]
                    left_position[1] += y_pian[i]
                    right_position[1] += y_pian[i]
                    left = get_position_value(left_position, radius=50)
                    right = get_position_value(right_position, radius=50)
                    self.env.adam.set_position(left, right)
                # zero
                set_adam_position('zero', wait=True)
                # 画圆
                # self.set_adam_circle('circle0', 'circle1', 100, start_point='zero', circle_speed=500)
                # 比爱心
                set_adam_position('ai-zhong', left_speed=400, right_speed=400)
                set_adam_position('ai', left_speed=400, right_speed=400)
                # 爱心左右移动
                for i in range(2):
                    set_adam_position('ai-left')
                    set_adam_position('ai-right')
                # 回到标准爱心位置
                set_adam_position('ai')
                # 回到舞蹈初始点
                set_adam_position('ai-zhong', left_speed=400, right_speed=400)
                set_adam_position('zero', left_speed=400, right_speed=400, wait=True)
                set_adam_position('prepare', wait=True)
                logger.info('dance use_time={}'.format(time.perf_counter() - start_time))

        def dance6():
            logger.info('dance6!!!')
            AudioInterface.music('Saturday_night_fever_dance.mp3')

            for i in range(3):  # 7
                # 抱胸姿势
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(  #
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                               'wait': False},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                              'wait': True}
                    )
                # 右手胸前摇晃
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)
                        self.right.set_position(x=515, y=-161, z=593, roll=64, pitch=17.7, yaw=126, speed=800,
                                                wait=True)

                # 左右手交替胸前摇晃
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': False},
                            left={'x': 515, 'y': 161, 'z': 593, 'roll': -64, 'pitch': 17.7, 'yaw': -126, 'speed': 800,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 515, 'y': -161, 'z': 593, 'roll': 64, 'pitch': 17.7, 'yaw': 126, 'speed': 800,
                                   'wait': False},
                            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': True}
                        )
                # 两只手交替往前伸出
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': False},
                            right={'x': 505, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': True}
                        )
                        self.env.adam.set_position(
                            left={'x': 505, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': False},
                            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': True}
                        )
                # 右手挥手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(x=245, y=-437, z=908, roll=22, pitch=-5, yaw=1, speed=800, wait=False)
                        self.right.set_position(x=278, y=-242, z=908, roll=-15, pitch=1, yaw=-1, speed=800, wait=False)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)

                # 左手挥手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_position(x=245, y=437, z=908, roll=-22, pitch=-5, yaw=1, speed=800, wait=False)
                        self.left.set_position(x=278, y=242, z=908, roll=15, pitch=1, yaw=-1, speed=800, wait=False)
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                              'wait': False},
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                               'wait': True}
                    )

        def run_dance(choice):
            try:
                # self.task_status = AdamTaskStatus.dancing
                self.goto_gripper_position(Arm.left, 0, wait=False)
                self.goto_gripper_position(Arm.right, 0, wait=False)
                if choice != 5:
                    left_angles, right_angles = self.get_initial_position()
                    logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
                    self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                                  dict(angle=right_angles, speed=20, wait=True))
                # self.check_adam_goto_initial_position()
                AudioInterface.stop()
                choice = choice
                if choice == 1:
                    logger.info('run dance1')
                    dance1()
                elif choice == 2:
                    logger.info('run dance2')
                    dance2()
                elif choice == 3:
                    logger.info('run dance3')
                    dance3()
                elif choice == 4:
                    logger.info('run dance4')
                    dance4()
                elif choice == 5:
                    logger.info('run dance5')
                    dance5()
                elif choice == 6:
                    logger.info('run dance6')
                    dance6()
                self.goto_standby_pose()
                # self.task_status = AdamTaskStatus.idle
            except Exception as e:
                logger.error('random dance have a error is {}'.format(str(e)))
                logger.error(traceback.format_exc())
            finally:
                AudioInterface.stop()
                self.env.init_adam()
                # self.task_status = AdamTaskStatus.idle

        self.stop_and_goto_zero()
        if self.task_status != AdamTaskStatus.idle:
            return self.task_status
        self.task_status = AdamTaskStatus.dancing
        t = threading.Thread(target=run_dance, args=(choice,))
        t.setDaemon(True)
        t.start()
        t.join()
        if self.task_status != AdamTaskStatus.making:
            self.task_status = AdamTaskStatus.idle
        return self.task_status

    def making_to_dance1(self):
        """告白舞"""

        self.task_status = AdamTaskStatus.dancing

        logger.info('making_to_dance1!!!')

        self.env.adam.set_tcp_offset(dict(offset=[0] * 6), dict(offset=[0] * 6))
        self.env.adam.set_state(dict(state=0), dict(state=0))
        default_speed = 600
        start_time = time.perf_counter()

        # 回到作揖状态
        left_angles, right_angles = self.get_initial_position()
        logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
        self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                      dict(angle=right_angles, speed=20, wait=True))
        AudioInterface.music('Oops.mp3')

        def get_position_value(position, **kwargs):
            v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
            value = dict(zip(v, position))
            kwargs.setdefault('speed', 1000)
            kwargs.setdefault('mvacc', 1000)
            return dict(value, **kwargs)

        def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
            left_speed = left_speed or default_speed
            right_speed = right_speed or default_speed
            left = get_position_value(data[Arm.left][point_name]['position'],
                                      wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
            right = get_position_value(data[Arm.right][point_name]['position'],
                                       wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
            self.env.adam.set_position(left, right)

        def get_next_point_speed(point_name):
            left_p, right_p = self.env.adam.position
            [x1, y1, z1] = left_p[:3]
            [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
            left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            [x1, y1, z1] = right_p[:3]
            [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
            right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            if left_d > right_d:
                s = int(left_d / right_d * default_speed)
                return default_speed, s
            else:
                s = int(left_d / right_d * default_speed)
                return s, default_speed

        data = utils.read_resource_json('/adam/data/dance1.json')
        for i in range(1):
            # 回到舞蹈初始点
            set_adam_position('zero', wait=True)
            # 同时运动到挥手位置
            left_speed, right_speed = get_next_point_speed('huang-you')
            set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
            # 左右挥手
            start_hui_time = time.perf_counter()
            for i in range(4):
                set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
            logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))

            if self.is_coffee_finished == True:
                break
            # zero
            set_adam_position('zero', wait=True)
            # 比爱心
            set_adam_position('ai-zhong', left_speed=400, right_speed=400)
            set_adam_position('ai', left_speed=400, right_speed=400)
            # 爱心左右移动
            for i in range(4):
                set_adam_position('ai-left')
                set_adam_position('ai-right')
            # 回到标准爱心位置
            set_adam_position('ai', wait=True)

            logger.info('dance use_time={}'.format(time.perf_counter() - start_time))

        # AudioInterface.stop()
        self.env.init_adam()

    def ring_bell_prepare(self):
        """敲钟"""
        self.task_status = AdamTaskStatus.prepare

        self.env.adam.set_servo_angle(
            right={'angle': [-145, 50, -80, 35, 15, 30], 'speed': 25, 'wait': True}
        )

    def ring_bell_start(self):
        """敲钟"""
        self.task_status = AdamTaskStatus.celebrating

        self.env.adam.set_servo_angle(
            right={'angle': [-155, 93, -145, 35, 15, 35], 'speed': 100, 'wait': True}
        )

        self.env.adam.set_servo_angle(
            left={'angle': [29, 100, -150, -176, 36, 88], 'speed': 40, 'wait': False}
        )
        for i in range(10):
            # self.left.set_position(x=245, y=437, z=908, roll=-22, pitch=-5, yaw=1, speed=200, wait=False)
            # self.left.set_position(x=278, y=242, z=908, roll=15, pitch=1, yaw=-1, speed=200, wait=False)

            self.env.adam.set_servo_angle(
                left={'angle': [29, 100, -150, -176, 36, 88], 'speed': 25, 'wait': False}
            )
            self.env.adam.set_servo_angle(
                left={'angle': [29, 100, -124, -176, 36, 88], 'speed': 25, 'wait': False}
            )

            # self.left.set_position(x=500, y=180, z=1100, roll=-33, pitch=-5, yaw=0.5, speed=100, wait=False)
            # self.left.set_position(x=500, y=-140, z=1050, roll=32, pitch=5, yaw=-4, speed=100, wait=False)

    def parallel_arms(self):
        """初始位置"""

        left_Pos1 = {'x': 385, 'y': -180, 'z': 590, 'roll': 90, 'pitch': 90, 'yaw': 0}
        right_Pos1 = {'x': 506, 'y': 133, 'z': 350, 'roll': -90, 'pitch': 90, 'yaw': 0}
        speed = 50
        self.env.adam.set_position(
            left={**left_Pos1, 'speed': speed, 'wait': True},
            right={**right_Pos1, 'speed': speed, 'wait': True},
        )

    def back_standby_pose(self):
        # logger.debug('adam is dancing now, stop and goto zero')
        self.env.adam.set_state(dict(state=4), dict(state=4))
        self.task_status = AdamTaskStatus.making  # temp
        # 停止播放音乐
        AudioInterface.stop()
        logger.warning("adam stop and wait 2 seconds")
        time.sleep(2)
        self.left.motion_enable()
        self.left.clean_error()
        self.left.clean_warn()
        self.left.set_state(0)
        self.right.motion_enable()
        self.right.clean_error()
        self.right.clean_warn()
        self.right.set_state(0)

        self.goto_standby_pose()
        logger.warning("adam stop and goto zero finish")
        print(f"self.task_status: {self.task_status}")
        self.task_status = AdamTaskStatus.idle
        return {'msg': 'ok', 'status': self.task_status}


class QueeyCoffeeThread(threading.Thread):
    def __init__(self, coffee_driver: CoffeeDriver):
        super().__init__()
        self.coffee_driver = coffee_driver
        self.coffee_status = dict(status=self.coffee_driver.last_status.get('system_status', ''),
                                  error_msg=self.coffee_driver.last_status.get('error_msg', []))
        self.run_flag = True
        self.bean_out_flag = False

    def pause(self):
        self.run_flag = False

    def proceed(self):
        self.run_flag = True

    def run(self):
        while self.run_flag:
            try:
                query_status = self.coffee_driver.query_status()
            except Exception as e:
                AudioInterface.gtts(str(e))
                query_status = {'system_status': 'UNKNOWN'}
            status = query_status.get('system_status')
            error_msg = query_status.get('error_msg', [])
            self.coffee_status = dict(status=status, error_msg=error_msg)
            if COFFEE_STATUS.get('error_msg', {}).get('11') in error_msg:
                CoffeeInterface.bean_out()
                self.bean_out_flag = True
            else:
                if self.bean_out_flag:
                    CoffeeInterface.bean_reset()
                    self.bean_out_flag = False
            for code in query_status.get('error_code', []):
                filename = 'coffee_error{}.mp3'.format(code)
                voice = os.path.join(audio_dir, 'voices', filename)
                AudioInterface.gtts(voice)
            time.sleep(60)  # 每分钟查询一次咖啡机状态
