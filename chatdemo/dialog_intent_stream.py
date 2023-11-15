import argparse
import os
import queue
import struct
import uuid
from collections import deque

import openai
import pvporcupine
import pyaudio
from google.cloud import dialogflow

from gtts import GTTS

credential_path = "./adamtts-360502-dd4287183c47.json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        info = self._audio_interface.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            if (self._audio_interface.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                device = self._audio_interface.get_device_info_by_host_api_device_index(0, i)
                print("Input Device id {} - {}, {} ".format(i, device.get('name'), device.get('defaultSampleRate')))
        self._audio_stream = self._audio_interface.open(
            input_device_index=5,
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        if not self.closed:
            # print(frame_count, self._buff.qsize())
            self._buff.put(in_data)
        return None, pyaudio.paContinue
        # return None, pyaudio.paComplete

    def pause(self):
        self.closed = True
        self._buff.queue.clear()
        # print('paused')

    def proceed(self):
        self.closed = False
        # print('proceed')

    def wake_generator(self):
        while not self.closed:
            chunk = self._buff.get()
            # chunk = self._audio_stream.read(512 * 3)
            data = [0] * 512
            data = list(struct.unpack('h' * 512 * 3, chunk))[0::3]
            # while data is not :
            #     data = list(struct.unpack('h' * int(len(chunk) / 2), chunk))
            # return data
            yield data

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                print('none1')
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b"".join(data)

# [START dialogflow_detect_intent_streaming]
def detect_intent_stream(project_id, session_id, input_device_index, language_code, stream):
    """Returns the result of detect intent with streaming audio as input.
    Using the same `session_id` between requests allows continuation
    of the conversation."""

    session_client = dialogflow.SessionsClient()

    # Note: hard coding audio_encoding and sample_rate_hertz for simplicity.
    audio_encoding = dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16
    sample_rate_hertz = 48000

    session_path = session_client.session_path(project_id, session_id)
    # print("Session path: {}\n".format(session_path))

    def request_generator(audio_config, output_config):
        query_input = dialogflow.QueryInput(audio_config=audio_config)

        # The first request contains the configuration.
        yield dialogflow.StreamingDetectIntentRequest(
            session=session_path, query_input=query_input
        )

        # Here we are reading small chunks of audio data from a local
        # audio file.  In practice these chunks should come from
        # an audio input device.
        print('start...')
        chunk_gene = stream.generator()
        while True:
            yield dialogflow.StreamingDetectIntentRequest(input_audio=next(chunk_gene))

    audio_config = dialogflow.InputAudioConfig(
        audio_encoding=audio_encoding,
        language_code=language_code,
        sample_rate_hertz=sample_rate_hertz,
        single_utterance=True
    )

    output_config = dialogflow.OutputAudioConfig(audio_encoding=audio_encoding, sample_rate_hertz=sample_rate_hertz)

    requests = request_generator(audio_config, output_config)
    responses = session_client.streaming_detect_intent(requests=requests)

    # print("=" * 20)
    for response in responses:
        pass
    #     print(
    #         'Intermediate transcript: "{}".'.format(
    #             response.recognition_result.transcript
    #         )
    #     )

    # Note: The result from the last response is the final transcript along
    # with the detected content.
    query_result = response.query_result

    # print("=" * 20)
    # print("Query text: {}".format(query_result.query_text))
    # print(
    #     "Detected intent: {} (confidence: {})\n".format(
    #         query_result.intent.display_name, query_result.intent_detection_confidence
    #     )
    # )
    # print("Fulfillment text: {}\n".format(query_result.fulfillment_text))
    if query_result.intent_detection_confidence > 0.8:
        return query_result.fulfillment_text, query_result.query_text.strip()
    else:
        return 'pass', query_result.query_text.strip()


def send2GPT(records):
    gpt_response = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                messages=records,
                                                temperature=1.5,
                                                max_tokens=100
                                                )
    response_text = gpt_response['choices'][0]['message']['content']
    recent_content.append({"role": "assistant", "content": response_text.strip()})
    #print('gpt response = [{}]'.format(response_text.strip()))
    return response_text.strip()
    # gt.generate_mp3(response_text.strip())
    #
    # gt.play_voice()


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(
    #     description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    # )
    # parser.add_argument(
    #     "--project-id", help="Project/agent id.  Required.", required=True
    # )
    # parser.add_argument(
    #     "--session-id",
    #     help="Identifier of the DetectIntent session. " "Defaults to a random UUID.",
    #     default=str(uuid.uuid4()),
    # )
    # parser.add_argument(
    #     "--language-code",
    #     help='Language code of the query. Defaults to "en-US".',
    #     default="en-US",
    # )
    # parser.add_argument(
    #     "--audio-file-path", help="Path to the audio file.", required=True
    # )
    #
    # args = parser.parse_args()
    # dialogflow constants
    project_id = 'adamtts-360502'
    session_id = str(uuid.uuid4())
    # audio_file_path = ''
    input_device_index = 1
    language_code = "en-US"

    # openai constants
    openai.api_key = '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'
    ROLE_SETTING = [{"role": "system",
                     "content": "You are a robot designed by Richtech Corporation and your name is Adam. You are in charge of making coffee and boba milk tea and communicating with customers. You are very humorous. The coffee you can make includes: Cappuccino, Lattee, Americano; and the boba milk tea you can make: Hong Kong Style Milk Tea, Taro Milk Tea, Cold Brew Coffee, etc. You can let customers see the menu in the store for details."}]

    # pvporcupine settings
    porcupine = pvporcupine.create(
        access_key='i/qSJyQsdRUWTUGJg1S2uTHKC9U7AU1GxvQZo7Oc2hn6DJ39teyrWA==',
        library_path=pvporcupine.LIBRARY_PATH,
        model_path=pvporcupine.MODEL_PATH,
        keyword_paths=['Hi-adam_en_linux_v2_1_0.ppn'],
        sensitivities=[0.5])

    # text to speech
    gt = GTTS('response.mp3')

    print('say [hey adam] to wake me up')
    # open microphone
    with MicrophoneStream(48000, 512 * 3) as stream:
        waked = False
        recent_content = deque(maxlen=20)
        wake_generator = stream.wake_generator()
        while True:
            if not waked:
                print('Say ["hey adam"] to wake me up; say ["bye"] to end the talks')
            while not waked:
                pcm = next(wake_generator)
                # print(pcm)
                result = porcupine.process(pcm)
                # print(result)
                if result >= 0:
                    print('Waked up!')
                    waked = True
                    recent_content.clear()
                    stream.pause()
                    gt.play_voice('wake_up.mp3')
                    stream.proceed()
                    # print('hi, may i help you?')
                    break

            dia_response, audio_text = detect_intent_stream(project_id, session_id, input_device_index, language_code, stream)
            if audio_text:
                audio_text = audio_text.strip()
                stream.pause()
                print('you said [{}]'.format(audio_text))
                if audio_text == 'bye':
                    waked = False
                    recent_content.clear()
                    del wake_generator
                    stream.proceed()
                    wake_generator = stream.wake_generator()
                    # print('need to wake up again')
                    continue
                if dia_response == 'pass':
                    #print('---chatgpt---')
                    recent_content.append({"role": "user", "content": audio_text})
                    chats = ROLE_SETTING + list(recent_content)
                    #print('send [{}] to chatGPT'.format(chats))
                    gpt_response = send2GPT(chats)
                    recent_content.append({"role": "assistant", "content": gpt_response})
                    print('gpt response = [{}]'.format(gpt_response))
                    gt.generate_mp3(gpt_response)
                    gt.play_voice()
                    stream.proceed()
                else:
                    #print('---dialogflow---')
                    recent_content.append({"role": "user", "content": audio_text})
                    recent_content.append({"role": "assistant", "content": dia_response})
                    print('dialog response = [{}]'.format(dia_response))
                    gt.generate_mp3(dia_response)
                    gt.play_voice()
                    stream.proceed()
