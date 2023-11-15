#
# Copyright 2020-2021 Picovoice Inc.
#
# You may not use this file except in compliance with the license. A copy of the license is located in the "LICENSE"
# file accompanying this source.
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
import sys
import threading
import time
import traceback

sys.path.append('..')
import argparse
import json
import os
import struct
import wave
from threading import Thread

from picovoice import *
from pvrecorder import PvRecorder
from loguru import logger
from socket import *

from common import conf, utils
from common.schemas import center as center_schema
from common import conf
from common.api import AudioInterface, ExceptionInterface, CenterInterface
from common.define import ExceptionType


dest = ('255.255.255.255', 20020)
broadcast_socket = socket(AF_INET, SOCK_DGRAM)
broadcast_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, True)

def play(obj, str1):
    AudioInterface.sound(str1)


class PicovoiceDemo(Thread):
    def __init__(
            self,
            access_key,
            audio_device_index,
            keyword_path,
            context_path,
            porcupine_library_path=None,
            porcupine_model_path=None,
            porcupine_sensitivity=0.5,
            rhino_library_path=None,
            rhino_model_path=None,
            rhino_sensitivity=0.5,
            require_endpoint=True,
            output_path=None):
        super(PicovoiceDemo, self).__init__()

        try:
            self._picovoice = Picovoice(
                access_key=access_key,
                keyword_path=keyword_path,
                wake_word_callback=self._wake_word_callback,
                context_path=context_path,
                inference_callback=self._inference_callback,
                porcupine_library_path=porcupine_library_path,
                porcupine_model_path=porcupine_model_path,
                porcupine_sensitivity=porcupine_sensitivity,
                rhino_library_path=rhino_library_path,
                rhino_model_path=rhino_model_path,
                rhino_sensitivity=rhino_sensitivity,
                require_endpoint=require_endpoint)
        except PicovoiceInvalidArgumentError as e:
            logger.error("One or more arguments provided to Picovoice is invalid: {\n" +
                         f"\t{access_key=}\n" +
                         f"\t{keyword_path=}\n" +
                         f"\t{self._wake_word_callback=}\n" +
                         f"\t{context_path=}\n" +
                         f"\t{self._inference_callback=}\n" +
                         f"\t{porcupine_library_path=}\n" +
                         f"\t{porcupine_model_path=}\n" +
                         f"\t{porcupine_sensitivity=}\n" +
                         f"\t{rhino_library_path=}\n" +
                         f"\t{rhino_model_path=}\n" +
                         f"\t{rhino_sensitivity=}\n" +
                         f"\t{require_endpoint=}\n" +
                         "}")
            logger.error(f"If all other arguments seem valid, ensure that '{access_key}' is a valid AccessKey")
            raise e
        except PicovoiceActivationError as e:
            logger.error("AccessKey activation error")
            raise e
        except PicovoiceActivationLimitError as e:
            logger.error(f"AccessKey '{access_key}' has reached it's temporary device limit")
            raise e
        except PicovoiceActivationRefusedError as e:
            logger.error(f"AccessKey '{access_key}' refused")
            raise e
        except PicovoiceActivationThrottledError as e:
            logger.error(f"AccessKey '{access_key}' has been throttled")
            raise e
        except PicovoiceError as e:
            logger.error("Failed to initialize Picovoice")
            raise e

        self.audio_device_index = audio_device_index
        self.output_path = output_path

    # @staticmethod
    def _wake_word_callback(self):
        logger.info('[wake word]\n')

    # @staticmethod
    def _inference_callback(self, inference):
        intent_dict = {'intent': ''}
        if inference.is_understood:
            intent_dict['intent'] = inference.intent
            intent_dict['slots'] = inference.slots
            for slot, value in inference.slots.items():
                if value == 'Shaken':
                    threading.Thread(target=play, args=(self._picovoice, 'shaken.mp3')).start()
                    ts = int(time.time())
                    data = {"name": "", "mail": "", "phone": "", "debit_card": "", "credit_card": "", "order_number": str(ts), "order_status": "waiting", "drinks": ["Martini"]}
                    CenterInterface.new_order(data, 'richtech')
        else:
            logger.warning("Didn't understand the command")
        logger.info('intent_dict={}'.format(intent_dict))
        #broadcast_socket.sendto(json.dumps(intent_dict).encode(), dest)

    def run(self):
        recorder = None
        wav_file = None

        try:
            recorder = PvRecorder(device_index=self.audio_device_index, frame_length=self._picovoice.frame_length)
            recorder.start()

            if self.output_path is not None:
                wav_file = wave.open(self.output_path, "w")
                wav_file.setparams((1, 2, 16000, 512, "NONE", "NONE"))

            logger.info(f"Using device: {recorder.selected_device}")
            logger.info('[Listening ...]')

            while True:
                pcm = recorder.read()
                if wav_file is not None:
                    wav_file.writeframes(struct.pack("h" * len(pcm), *pcm))

                self._picovoice.process(pcm)
        except KeyboardInterrupt:
            sys.stdout.write('\b' * 2)
            logger.info('Stopping ...')
        finally:
            if recorder is not None:
                recorder.delete()

            if wav_file is not None:
                wav_file.close()

            self._picovoice.delete()

    @classmethod
    def show_audio_devices(cls):
        devices = PvRecorder.get_audio_devices()

        for i in range(len(devices)):
            logger.info(f'index: {i}, device name: {devices[i]}')


def main():
    PicovoiceDemo.show_audio_devices()
    picovoice_config = center_schema.WakeDemoConfig(**conf.get_wake_demo_config()).picovoice
    model_path = '../resource/wake'
    access_key = picovoice_config.access_key
    if len(access_key) < 10:
        logger.error("access_key={} length too short!".format(access_key))
        exit(-1)
    bin_path_file = os.listdir(model_path)
    keyword_path = [i for i in bin_path_file if i.endswith('.ppn')]
    context_path = [i for i in bin_path_file if i.endswith('.rhn')]
    if keyword_path:
        keyword_path = os.path.abspath(os.path.join(model_path, keyword_path[0]))
        logger.info('keyword_path={}'.format(keyword_path))
    else:
        logger.error("keyword_path .ppn not exist in {}".format(model_path))
        exit(-1)
    if context_path:
        context_path = os.path.abspath(os.path.join(model_path, context_path[0]))
        logger.info('context_path={}'.format(context_path))
    else:
        logger.error("context_path .rhn not exist in {}".format(model_path))
        exit(-1)

    porcupine_library_path = None
    porcupine_model_path = None
    porcupine_sensitivity = 0.5
    rhino_library_path = None
    rhino_model_path = None
    rhino_sensitivity = 0.5
    require_endpoint = True
    audio_device_index = int(picovoice_config.audio_device_index)
    logger.info('audio_device_index={}'.format(audio_device_index))
    output_path = None

    try:
        ExceptionInterface.clear_error(ExceptionType.wake_init_failed)
        PicovoiceDemo(
            access_key=access_key,
            audio_device_index=audio_device_index,
            keyword_path=keyword_path,
            context_path=context_path,
            porcupine_library_path=porcupine_library_path,
            porcupine_model_path=porcupine_model_path,
            porcupine_sensitivity=porcupine_sensitivity,
            rhino_library_path=rhino_library_path,
            rhino_model_path=rhino_model_path,
            rhino_sensitivity=rhino_sensitivity,
            require_endpoint=require_endpoint,
            output_path=output_path).run()
    except Exception as e:
        ExceptionInterface.add_error(ExceptionType.wake_init_failed, str(e))
        time.sleep(3)
        exit(-1)


if __name__ == '__main__':
    MODULE = utils.get_file_dir_name(__file__)
    LOG_PATH = conf.get_log_path(MODULE)
    logger.add(LOG_PATH)
    main()
