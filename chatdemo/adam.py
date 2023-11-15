import random
import time

from xarm.wrapper import XArmAPI


class Adam:
    def __init__(self, left_ip, right_ip):
        self.left = XArmAPI(left_ip)
        self.right = XArmAPI(right_ip)

    @property
    def right_init_pose(self):
        return {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}

    @property
    def left_init_pose(self):
        return {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

    def init_arm(self):
        self.left.motion_enable()
        self.left.clean_error()
        self.left.clean_warn()
        self.left.set_collision_sensitivity(0)
        self.left.set_state()

        self.right.motion_enable()
        self.right.clean_error()
        self.right.clean_warn()
        self.right.set_collision_sensitivity(0)
        self.right.set_state()
        time.sleep(0.5)

    def goto_standby(self, speed=100):
        self.left.set_position(**self.left_init_pose, wait=False, speed=speed, radius=20)
        self.right.set_position(**self.right_init_pose, wait=True, speed=speed, radius=20)

    # 右手往上抬
    def right_up(self, speed=100):
        right_pose1 = {'x': 355, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}
        self.right.set_position(**self.right_init_pose, wait=False, speed=speed, radius=20)
        self.right.set_position(**right_pose1, wait=False, speed=speed, radius=20)
        # self.right.set_position(**self.right_init_pose, wait=True, speed=speed, radius=20)   

    # 左手往上抬
    def left_up(self, speed=50):
        left_pose1 = {'x': 355, 'y': 100, 'z': 750, 'roll': 0, 'pitch': 60, 'yaw': -90}
        self.left.set_position(**self.left_init_pose, wait=False, speed=speed, radius=20)
        self.left.set_position(**left_pose1, wait=False, speed=speed, radius=20)
        # self.left.set_position(**self.left_init_pose, wait=True, speed=speed, radius=20)

    # 右手往前伸出
    def right_front(self, speed=100):
        right_pose2 = {'x': 555, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        self.right.set_position(**self.right_init_pose, wait=False, speed=speed, radius=20)
        self.right.set_position(**right_pose2, wait=False, speed=speed, radius=20)
        # self.right.set_position(**self.right_init_pose, wait=True, speed=speed, radius=20)

    # 左手往前伸出
    def left_front(self, speed=50):
        left_pose2 = {'x': 455, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
        self.left.set_position(**self.left_init_pose, wait=False, speed=speed, radius=20)
        self.left.set_position(**left_pose2, wait=False, speed=speed, radius=20)
        # self.left.set_position(**self.left_init_pose, wait=True, speed=speed, radius=20)

    # 右手往右上运动
    def right_right_up(self, speed=100):
        right_pose3 = {'x': 355, 'y': -200, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}
        self.right.set_position(**self.right_init_pose, wait=False, speed=speed, radius=20)
        self.right.set_position(**right_pose3, wait=False, speed=speed, radius=20)

    # 左手往左上运动
    def left_left_up(self, speed=50):
        left_pose3 = {'x': 355, 'y': 200, 'z': 750, 'roll': 0, 'pitch': 60, 'yaw': -90}
        self.left.set_position(**self.left_init_pose, wait=False, speed=speed, radius=20)
        self.left.set_position(**left_pose3, wait=False, speed=speed, radius=20)

    # 挥手动作
    def hello(self, speed=400):
        right_pose4 = {'x': 245, 'y': -437, 'z': 908, 'roll': 22, 'pitch': -5, 'yaw': 1}
        right_pose5 = {'x': 278, 'y': -242, 'z': 908, 'roll': -15, 'pitch': 1, 'yaw': -1}
        for i in range(2):
            self.right.set_position(**right_pose4, wait=False, speed=speed, radius=20)
            self.right.set_position(**right_pose5, wait=False, speed=speed, radius=20)

    def choose_action(self, i):
        if i == 1:
            self.right_up(200)
        elif i == 2:
            self.right_front(200)
        elif i == 3:
            self.right_right_up(200)
        elif i == 4:
            self.left_up(100)
        elif i == 5:
            self.left_front(100)
        elif i == 6:
            self.left_left_up(100)

    def generate_action_index(self):
        all_actions = {1, 2, 3, 4, 5, 6}
        result = [random.choice(list(all_actions))]
        for i in range(2, 6):
            result.append(list(all_actions - {result[i - 1], result[i - 1] + 3}))

    def random_action(self):
        all_actions = [1, 2, 3, 4, 5, 6]
        random.shuffle(all_actions)
        for index in all_actions:
            self.choose_action(index)
        self.goto_standby(500)

    def say_hi(self):
        self.goto_standby()
        self.hello()
        self.goto_standby()

