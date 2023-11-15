import evdev

from evdev import InputDevice, categorize # import * is evil :)

# dev = InputDevice('/dev/input/event1')
#
# # Provided as an example taken from my own keyboard attached to a Centos 6 box:
#
# scancodes = {
#
# # Scancode: ASCIICode
#
# 0: None, 1: u'ESC', 2: u'1', 3: u'2', 4: u'3', 5: u'4', 6: u'5', 7: u'6', 8: u'7', 9: u'8',
#
# 10: u'9', 11: u'0', 12: u'-', 13: u'=', 14: u'BKSP', 15: u'TAB', 16: u'Q', 17: u'W', 18: u'E', 19: u'R',
#
# 20: u'T', 21: u'Y', 22: u'U', 23: u'I', 24: u'O', 25: u'P', 26: u'[', 27: u']', 28: u'CRLF', 29: u'LCTRL',
#
# 30: u'A', 31: u'S', 32: u'D', 33: u'F', 34: u'G', 35: u'H', 36: u'J', 37: u'K', 38: u'L', 39: u';',
#
# 40: u'"', 41: u'`', 42: u'LSHFT', 43: u'\\', 44: u'Z', 45: u'X', 46: u'C', 47: u'V', 48: u'B', 49: u'N',
#
# 50: u'M', 51: u',', 52: u'.', 53: u'/', 54: u'RSHFT', 56: u'LALT', 100: u'RALT'
#
# }

# for event in dev.read_loop():
#
#     if event.type == evdev.ecodes.EV_KEY:
#
#         data = evdev.categorize(event) # Save the event temporarily to introspect it
#
#     if data.keystate == 1: # Down events only
#
#         key_lookup = scancodes.get(data.scancode) or u'UNKNOWN:{}'.format(data.scancode) # Lookup or return UNKNOWN:XX
#
#         print(u'You Pressed the {} key!'.format(key_lookup)) # Print it all out!
# devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
# for device in devices:
#     print(device.path, device.name, device.phys)


# devices = map(InputDevice, evdev.list_devices())
#
# keys = {
#     2: 1,
#     3: 2,
#     4: 3,
#     5: 4,
#     6: 5,
#     7: 6,
#     8: 7,
#     9: 8,
#     10: 9,
#     11: 0,
# }
# dev = None
# for d in devices:
#     if d.name == 'Symbol Technologies, Inc, 2008 Symbol Bar Code Scanner':
#         print('%-20s %-32s %s' % (d.fn, d.name, d.phys))
#         dev = InputDevice(d.fn)
#         break
#
# if dev is not None:
#     code = []
#     for event in dev.read_loop():
#         if event.type == evdev.ecodes.EV_KEY:
#             if event.value == 00:
#                 if event.code != 96:
#                     try:
#                         code.append(keys[event.code])
#                     except:
#                         code.append('-')
#                 else:
#                     card = "".join(map(str, code))
#                     print(card)
#
#                     code = []
#                     card = ""

#!/usr/bin/env python
#coding: utf-8
import os

# 源目录
deviceFilePath = '/sys/class/input/'

def showDevice():
    os.chdir(deviceFilePath)
    for i in os.listdir(os.getcwd()):
        namePath = deviceFilePath + i + '/device/name'
        if os.path.isfile(namePath):
            print("Name: %s Device: %s" % (i, open(namePath).read()))
