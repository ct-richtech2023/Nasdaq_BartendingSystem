import time
from xarm import XArmAPI

arm = XArmAPI("192.168.2.226")
origin = arm.tcp_jerk
code = arm.set_tcp_jerk(2233)
time.sleep(1)
arm.save_conf()
time.sleep(1)
current = arm.tcp_jerk
print("origin={} code={} current={}".format(origin, code, current))
