import os
import threading

from xarm.wrapper import XArmAPI

from adam.dual import AdamRobot

left = XArmAPI('192.168.2.226')
right = XArmAPI('192.168.2.240')

adam = AdamRobot(left, right)

right.motion_enable()
right.set_state()
right.set_mode(0)

left.motion_enable()
left.set_state()
left.set_mode(0)


def play_music():
    cmd = 'ffplay -nodisp -autoexit /home/ubuntu/Documents/RichTech/gitee/CoffeeRoom/resource/audio/musics/clap_snap.mp3'
    os.system(cmd)


t = threading.Thread(target=play_music)
t.setDaemon(True)
t.start()

if True:
    adam.set_position(
        left={'x': 305, 'y': 550, 'z': 250, 'roll': -90, 'pitch': 0, 'yaw': -90, 'speed': 250, 'wait': True},
        right={'x': 305, 'y': -550, 'z': 250, 'roll': 90, 'pitch': 0, 'yaw': 90, 'speed': 250, 'wait': True}
    )
    # exit()
    for i in range(2):
        adam.set_position(
            left={'x': 205, 'y': 550, 'z': 250, 'roll': -110, 'pitch': 0, 'yaw': -90, 'speed': 500},
            right={'x': 405, 'y': -550, 'z': 350, 'roll': 70, 'pitch': 0, 'yaw': 90, 'speed': 500}
        )
        adam.set_position(
            left={'x': 405, 'y': 550, 'z': 350, 'roll': -70, 'pitch': 0, 'yaw': -90, 'speed': 500},
            right={'x': 205, 'y': -550, 'z': 250, 'roll': 110, 'pitch': 0, 'yaw': 90, 'speed': 500}
        )
adam.set_position(
    left={'x': 305, 'y': 550, 'z': 250, 'roll': -90, 'pitch': 0, 'yaw': -90, 'speed': 250, 'wait': True},
    right={'x': 305, 'y': -550, 'z': 250, 'roll': 90, 'pitch': 0, 'yaw': 90, 'speed': 250, 'wait': True}
)
# exit()
#
#
if True:
    adam.set_position(
        left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250, 'wait': True},
        right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 400, 'wait': True}
    )

    for i in range(2):
        adam.set_position(
            left={'x': 500, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
            right={'x': 500, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250}
        )
        adam.set_position(
            left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
            right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250}
        )

#
if True:

    adam.set_position(
        left={'x': 580, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': True},
        right={'x': 580, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': True}
    )

    for i in range(2):
        adam.move_circle(
            left={'pose1': [580, 200, 900, 0, 0, 0], 'pose2': [580, 0, 900, 0, 0, 0], 'percent': 100, 'speed': 250},
            right={'pose1': [580, -0, 900, 0, 0, 180], 'pose2': [580, -200, 900, 0, 0, 180], 'percent': 100,
                   'speed': 250}
        )
#
adam.set_position(
    left={'x': 580, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': True},
    right={'x': 580, 'y': -200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': True}
)
adam.set_position(
    left={'x': 0, 'y': 60, 'z': 900, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
    right={'x': 0, 'y': -60, 'z': 900, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
)

for i in range(2):
    adam.set_position(
        left={'x': 0, 'y': 160, 'z': 900, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': False},
        right={'x': 0, 'y': 40, 'z': 900, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': False}
    )
    adam.set_position(
        left={'x': 0, 'y': -40, 'z': 900, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': False},
        right={'x': 0, 'y': -160, 'z': 900, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': False}
    )
adam.set_position(
    left={'x': 0, 'y': 60, 'z': 900, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
    right={'x': 0, 'y': -60, 'z': 900, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
)

adam.set_servo_angle(
    left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 20, 'wait': True},
    right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 27, 'wait': True},
)
