import time
from typing import Optional

import requests
import threading
from loguru import logger
from pydantic import BaseModel
from serial import Serial

#ser = Serial('/dev/ttyACM2', 9600, timeout=1, write_timeout=10)
#time.sleep(1)

class Arduino:
    def __init__(self, dev_name):
        self.ser = Serial(dev_name, 9600, timeout=1)
        time.sleep(1)
        #pass

    def send_msgs(self, chars: list):
        if not ser.isOpen():  # Turn on serial port.
            ser.open()
            time.sleep(1)

        for char in chars:
            ser.write(char.encode('utf-8'))
            time.sleep(0.1)

        #if self.ser.isOpen():
        #    self.ser.close()
        #    time.sleep(0.1)

    def send_one_msg(self, char):
        try:
            ser = Serial('/dev/ttyACM0', 9600, timeout=1, write_timeout=10)
        except:
            ser = Serial('/dev/ttyACM1', 9600, timeout=1, write_timeout=10)
            
        time.sleep(0.1)
        if not ser.isOpen():  # Turn on serial port.
            ser.open()
            logger.info('opened again==========================================================')
            time.sleep(1)

        ser.write(char.encode('utf-8'))
        time.sleep(0.1)
        logger.info('send char {}'.format(char))

        if ser.isOpen():
            time.sleep(0.5)
            ser.close()
           

    def read_msg(self, min_len=20, split=True):
        """
        return entire line read from ser;
        if split=True, split the line by ',' and return the list
        """
        #ser = Serial('/dev/ttyACM2', 9600, timeout=1)
        #time.sleep(0.1)
        if not self.ser.isOpen():  # Turn on serial port.
            self.ser.open()
            logger.debug('need open in read')
            time.sleep(1)
        self.ser.reset_input_buffer()
        line = self.ser.readline().decode('utf-8', 'ignore')
        logger.info("line is {}".format(line))
        
        #if self.ser.isOpen():
        #    self.ser.close()
        #    time.sleep(0.1)

        if not split:
            return line
        else:
            if line and len(line) >= min_len:
                split_list = line.split(",")
                for i in range(len(split_list)):
                    if split_list[i] == '' or split_list[i] == None:
                        split_list[i] = 0
                return split_list
        return [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def close(self):
        pass
        #if ser.isOpen():
        #    time.sleep(0.5)
        #    ser.close()
            # time.sleep(0.5)

    def open(self):
        pass
        #if not ser.isOpen():  # Turn on serial port.
        #    ser.open()
        #    logger.info('open')
        #    time.sleep(1)


class MachineConfig(BaseModel):
    machine: str
    num: int
    arduino_write: Optional[str]  # 向arduino发送什么字符
    arduino_read: Optional[str]  # 从arduino流量列表读取第几个示数
    delay_time: Optional[int]  # 通过时间控制开关的话，打开时间
    type: Optional[str]  # 类型，根据时间开关为time， 根据流量计开关为volume


class AdamOneArduino:
    def __init__(self, dev_name):
        self.arduino = Arduino(dev_name)
        #self.arduino.send_one_msg('0')
        self.machine_config = None
        self.lock = threading.Lock()

    @staticmethod
    def init_config():
        """
        从数据库machine_config表，读取龙头 和 杯子 arduino相关的设置
        """
        url = "http://127.0.0.1:9001/coffee/machine/get"
        res = requests.get(url)
        machine_configs = {}
        if res.status_code == 200:
            machine_configs = res.json()
        machine_dict = {}
        for config in machine_configs:
            if config.get('machine') in ['tap', 'cup']:
                machine_dict[config.get('name')] = MachineConfig(**config)
        return machine_dict

    def refresh_config(self):
        self.machine_config = self.init_config()

    def read_line(self):
        self.arduino.open()
        end_time = time.time() + 60
        while time.time() < end_time:
            read_list = self.arduino.read_msg(min_len=25, split=True)
            logger.info('Check sensor value: {}'.format(read_list))
        # self.arduino.close()

    def open_port_together(self, open_dict):
        """
        一次性打开所有龙头
        open_dict: {'material_name': quantity}
        """
        self.lock.acquire()
        logger.info('open_port_together get lock')
        try:
            self.refresh_config()  # 每次使用前，重新读取数据库内容进行刷新
            self.arduino.open()  # 打开串口
            opened = []  # 已经打开的龙头列表
            closed = []  # 已经关闭的龙头列表
            for material, quantity in open_dict.items():
                config = self.machine_config.get(material)
                self.arduino.send_one_msg(config.arduino_write)  # 依次打开龙头
                opened.append(material)
                logger.debug('open material {} for {} ml'.format(material, quantity))
            start_time = time.time()  # 打开龙头时间，通过时间控制龙头开关的时候用到

            while len(closed) < len(opened):
                volume_list = self.arduino.read_msg(min_len=20, split=True)
                for material, quantity in open_dict.items():
                    config = self.machine_config.get(material)
                    close_char = chr(ord(str(config.arduino_write)) + 48)  # 数字字符转英文字符
                    if material not in closed:
                        # 只对没有关闭的进行判断
                        if config.type == 'time' and time.time() - start_time >= config.delay_time:
                            # 根据时间判断开关
                            self.arduino.send_one_msg(close_char)  # 发送英文字符进行关闭
                            closed.append(material)
                            logger.debug('closed {} after {} s'.format(material, config.delay_time))
                        elif config.type != 'time' and int(volume_list[int(config.arduino_read)]) >= quantity * 4:
                            # 根据流量计读数判断开关
                            self.arduino.send_one_msg(close_char)  # 发送英文字符进行关闭
                            closed.append(material)
                            logger.debug('close {} after {} ml'.format(material, quantity))
                time.sleep(0.1)
            self.arduino.close()  # 结束后关闭串口
        finally:
            self.arduino.send_one_msg('0')  # 关闭所有龙头
            self.arduino.close()
            self.lock.release()
            logger.info('open_port_together release lock')

    def open_port_one_by_one(self, open_dict):
        """
        关闭第一个龙头后再打开第二个
        open_dict: {'material_name': quantity}
        """
        self.lock.acquire()
        try:
            self.refresh_config()  # 每次使用前，重新读取数据库内容进行刷新
            self.arduino.open()  # 打开串口
            for material, quantity in open_dict.items():
                config = self.machine_config.get(material)
                if config.type == 'time':
                    # 如果是根据时间开关的，就根据延时设置开关
                    logger.debug('open material {} for {} s'.format(material, config.delay_time))
                    self.arduino.send_one_msg(config.arduino_write)  # 打开龙头
                    time.sleep(config.delay_time)
                    self.arduino.send_one_msg('0')  # 关闭所有龙头
                    logger.debug('close {} after {} s'.format(material, config.delay_time))
                else:
                    # 根据流量开关的，就不停读取流量计示数
                    self.arduino.send_one_msg(config.arduino_write)  # 打开龙头
                    logger.debug('open material {} for {} ml'.format(material, quantity))
                    close = False  # 退出while循环标志
                    while not close:
                        volume_list = self.arduino.read_msg(min_len=20, split=True)  # 从arduino读取一行根据','分割好的数据列表
                        if int(config.arduino_read) < len(volume_list):  # 防止读取位置超出列表长度引起的报错
                            if int(volume_list[int(config.arduino_read)]) >= quantity * 4:  # 流量大于所需数量，可以关闭了
                                self.arduino.send_one_msg('0')  # 关闭所有龙头
                                logger.debug('closed {} after {} ml'.format(material, quantity))
                                close = True  # 退出while循环标志
                        time.sleep(0.1)  # 等待0.1s后再次读取流量计示数
            self.arduino.close()  # 结束后关闭串口
        finally:
            self.arduino.send_one_msg('0')  # 关闭所有龙头
            self.lock.release()

    def check_cup_token(self, cup_name, distance=200):
        """
        cup_name: 杯子名称
        distance: 大于多少距离算成功
        """
        self.lock.acquire()
        logger.info('check_cup_token get lock')
        try:
            self.refresh_config()  # 每次使用前，重新读取数据库内容进行刷新
            self.arduino.open()  # 打开串口
            cup_config = self.machine_config.get(cup_name)
            max_distance = 0
            end_time = time.time() + 1
            while time.time() < end_time:
                read_list = self.arduino.read_msg(min_len=25, split=True)
                if int(cup_config.arduino_read) < len(read_list):
                    if int(read_list[int(cup_config.arduino_read)]) > max_distance:
                        max_distance = int(read_list[int(cup_config.arduino_read)])  # 记录1秒内的最大值
            self.arduino.close()  # 结束后关闭串口
            if max_distance > distance:
                logger.info('distance is {}, return True'.format(max_distance))
                return True
            
            logger.info('distance is {}, return False'.format(max_distance))
            return False
        finally:
            self.lock.release()
            logger.info('check_cup_token release lock')
            #pass



def main():
    if not ser.isOpen():  # Turn on serial port.
        logger.info('need open')
        ser.open()
    time.sleep(1)
    ser.write('1'.encode('utf-8'))
    time.sleep(1)
    ser.write('2'.encode('utf-8'))
    time.sleep(1)
    ser.write('3'.encode('utf-8'))
    time.sleep(3)
    ser.write('a'.encode('utf-8'))
    time.sleep(1)
    ser.write('b'.encode('utf-8'))
    time.sleep(1)
    ser.write('c'.encode('utf-8'))
    time.sleep(1)
    if ser.isOpen():
        logger.info('need close')
        ser.close()
    time.sleep(1)

def main2(ard):
    ser = Serial('/dev/ttyACM1', 9600, timeout=1, write_timeout=10)
    time.sleep(0.1)
    #ard.arduino.close()
    ard.arduino.open(ser)
    time.sleep(1)
    #ard.arduino.send_one_msg('1',ser)
    #time.sleep(1)
    #ard.arduino.send_one_msg('a')
    #ard.arduino.close(ser)
    return ser

def main3(ard):
    #ser = Serial('/dev/ttyACM2', 9600, timeout=1, write_timeout=10)
    #time.sleep(0.1)
    #ard.arduino.close()
    ard.arduino.open(ser)
    time.sleep(1)
    ard.arduino.send_one_msg('1',ser)
    #time.sleep(1)
    #ard.arduino.send_one_msg('b')
    ard.arduino.close(ser)

def main4(ard, txt):
    #ser = Serial('/dev/ttyACM2', 9600, timeout=1, write_timeout=10)
    #time.sleep(0.1)
    #ard.arduino.close()
    #ard.arduino.open(ser)
    #time.sleep(1)
    ard.arduino.send_one_msg(txt)
    #time.sleep(1)
    #ard.arduino.send_one_msg('c')
    #ard.arduino.close(ser)

if __name__ == '__main__':
    ard = AdamOneArduino('/dev/ttyACM1')
    logger.info('first time')
    #ser = main2(ard)
    logger.info('second time')
    #main3(ard)
    #logger.info('third time')
    #ard.open_port_together({'sea_salt_foam': 5})
    main4(ard,'0')
    #time.sleep(1)
    #main4(ard,'2')
    #time.sleep(1)
    #main4(ard,'b')
    #time.sleep(1)
    #main4(ard,'c')
    #time.sleep(1)
    #main4(ard,'a')

    #https://forums.raspberrypi.com/viewtopic.php?t=239621
    # ser = serial.Serial(port='/dev/ttyACM0', baudrate=9600, timeout=1, write_timeout=0.01)
    #ard = AdamOneArduino('/dev/ttyACM2')
    #ard.arduino.send_one_msg('1')
    #time.sleep(1)
    #ard.arduino.send_one_msg('2')
    #time.sleep(1)
    #ard.arduino.send_one_msg('3')
    #time.sleep(3)
    #ard.arduino.send_one_msg('a')
    #time.sleep(1)
    #ard.arduino.send_one_msg('b')
    #time.sleep(1)
    #ard.arduino.send_one_msg('c')

    #for i in range(3):
    #    ard.arduino.open()
    #    time.sleep(2)
    #    ard.arduino.close()
#     time.sleep(5)
#     for i in range(20):
#         logger.debug(i)
#         ard.arduino.read_msg(min_len=25)
#         # time.sleep(0.01)
#     ard.arduino.close()
    
