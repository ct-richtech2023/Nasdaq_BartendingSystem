import os
import struct
import time
import wave
from datetime import datetime
from threading import Thread

import pvporcupine
from pvrecorder import PvRecorder
from talk import start_talk



class WakeUpThread(Thread):
    """
    Microphone Demo for Porcupine wake word engine. It creates an input audio stream from a microphone, monitors it, and
    upon detecting the specified wake word(s) prints the detection time and wake word on console. It optionally saves
    the recorded audio into a file for further debugging.
    """

    def __init__(
            self,
            keyword_paths,
            sensitivities,
            input_device_index=None,
            output_path=None):

        """
        Constructor.
        :param library_path: Absolute path to Porcupine's dynamic library.
        :param model_path: Absolute path to the file containing model parameters.
        :param keyword_paths: Absolute paths to keyword model files.
        :param sensitivities: Sensitivities for detecting keywords. Each value should be a number within [0, 1]. A
        higher sensitivity results in fewer misses at the cost of increasing the false alarm rate. If not set 0.5 will
        be used.
        :param input_device_index: Optional argument. If provided, audio is recorded from this input device. Otherwise,
        the default audio input device is used.
        :param output_path: If provided recorded audio will be stored in this location at the end of the run.
        """

        super(WakeUpThread, self).__init__()
        # self._access_key = 'nieXE1gfiG2NVNm2FO7jLfln99pRF9X2bjJNg52oHDgVIFhsGAFniA=='
        self._access_key = 'i/qSJyQsdRUWTUGJg1S2uTHKC9U7AU1GxvQZo7Oc2hn6DJ39teyrWA=='
        self._library_path = pvporcupine.LIBRARY_PATH
        self._model_path = pvporcupine.MODEL_PATH
        self._keyword_paths = [keyword_paths]
        self._sensitivities = [sensitivities]
        self._input_device_index = input_device_index

        self._output_path = output_path

        self.paused = False

    def pause(self):
        self.paused = True

    def recover(self):
        self.paused = False

    def run(self):
        """
         Creates an input audio stream, instantiates an instance of Porcupine object, and monitors the audio stream for
         occurrences of the wake word(s). It prints the time of detection for each occurrence and the wake word.
         """

        keywords = list()
        for x in self._keyword_paths:
            keyword_phrase_part = os.path.basename(x).replace('.ppn', '').split('_')
            if len(keyword_phrase_part) > 6:
                keywords.append(' '.join(keyword_phrase_part[0:-6]))
            else:
                keywords.append(keyword_phrase_part[0])

        porcupine = None
        recorder = None
        wav_file = None
        try:
            porcupine = pvporcupine.create(
                access_key=self._access_key,
                library_path=self._library_path,
                model_path=self._model_path,
                keyword_paths=self._keyword_paths,
                sensitivities=self._sensitivities)

            recorder = PvRecorder(device_index=self._input_device_index, frame_length=porcupine.frame_length)
            # recorder.start()

            if self._output_path is not None:
                wav_file = wave.open(self._output_path, "w")
                wav_file.setparams((1, 2, 16000, 512, "NONE", "NONE"))

            print('Using device: %s', recorder.selected_device)

            print('Listening {')
            for keyword, sensitivity in zip(keywords, self._sensitivities):
                print('  %s (%.2f)' % (keyword, sensitivity))
            print('}')



            while True:
                while not self.paused:
                    recorder.start()
                    pcm = recorder.read()

                    if wav_file is not None:
                        wav_file.writeframes(struct.pack("h" * len(pcm), *pcm))

                    result = porcupine.process(pcm)
                    if result >= 0:
                        recorder.stop()
                        print('[%s] Detected %s' % (str(datetime.now()), keywords[result]))
                        # recorder.start()
                        start_talk()
                else:
                    recorder.stop()
                    # time.sleep(0.1)
        except pvporcupine.PorcupineInvalidArgumentError as e:
            args = (
                self._access_key,
                self._library_path,
                self._model_path,
                self._keyword_paths,
                self._sensitivities,
            )
            print("One or more arguments provided to Porcupine is invalid: ", args)
            print("If all other arguments seem valid, ensure that '%s' is a valid AccessKey" % self._access_key)
            raise e
        except pvporcupine.PorcupineActivationError as e:
            print("AccessKey activation error")
            raise e
        except pvporcupine.PorcupineActivationLimitError as e:
            print("AccessKey '%s' has reached it's temporary device limit" % self._access_key)
            raise e
        except pvporcupine.PorcupineActivationRefusedError as e:
            print("AccessKey '%s' refused" % self._access_key)
            raise e
        except pvporcupine.PorcupineActivationThrottledError as e:
            print("AccessKey '%s' has been throttled" % self._access_key)
            raise e
        except pvporcupine.PorcupineError as e:
            print("Failed to initialize Porcupine")
            raise e
        except KeyboardInterrupt:
            print('Stopping ...')
        finally:
            if porcupine is not None:
                porcupine.delete()

            if recorder is not None:
                recorder.delete()

            if wav_file is not None:
                wav_file.close()

    @classmethod
    def show_audio_devices(cls):
        devices = PvRecorder.get_audio_devices()

        for i in range(len(devices)):
            print('index: %d, device name: %s' % (i, devices[i]))


def main():
    # keyword_path = './wakeup.ppn'
    keyword_path = './Hi-adam_en_linux_v2_1_0.ppn'

    tt = WakeUpThread(
        keyword_paths=keyword_path,
        sensitivities=0.5,
        output_path='./test.mp3',
        input_device_index=4)
    tt.start()
    tt.pause()
    time.sleep(3)
    tt.recover()


if __name__ == '__main__':
    main()
