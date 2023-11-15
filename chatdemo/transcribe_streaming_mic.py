#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Speech API sample application using the streaming API.

NOTE: This module requires the additional dependency `pyaudio`. To install
using pip:

    pip install pyaudio

Example usage:
    python transcribe_streaming_mic.py
"""

# [START speech_transcribe_streaming_mic]
from __future__ import division

import json
import os
import re
import struct
import sys

import requests
from google.cloud import speech

import pyaudio
from six.moves import queue
import pvporcupine
from ChatGPTHttp import openai_create

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "careful.json"
flag = 1


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
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=512,
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
        print(frame_count, time_info, status_flags)
        self._buff.put(in_data)
        # print(in_data)
        return None, pyaudio.paContinue

    def wake_generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._audio_stream.read(512)
            data = list(struct.unpack('h' * 512, chunk))
            # while data is not :
            #     data = list(struct.unpack('h' * int(len(chunk) / 2), chunk))
            # return data
            yield data

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._audio_stream.read(CHUNK)
            # print('ss')
            yield chunk
            # chunk = self._buff.get(block=False)
            # if chunk is None:
            #     return
            # data = [chunk]
            #
            # # Now consume whatever other data's still buffered.
            # while True:
            #     try:
            #         chunk = self._buff.get(block=False)
            #         if chunk is None:
            #             print('none')
            #             return
            #         data.append(chunk)
            #     except queue.Empty:
            #         print('empty')
            #         break
            #
            # yield b"".join(data)


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        print('response', response)
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = " " * (num_chars_printed - len(transcript))
        if not result.is_final:
            # print("11")
            # print(transcript + overwrite_chars + "\r")
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print("result_speechtotext==", transcript + overwrite_chars)
            gpt_response = openai_create(transcript + overwrite_chars)
            print('gpt response', gpt_response)
            yield gpt_response
            # return transcript + overwrite_chars
            # flag = 0
            # # 调用ChatGPT
            # openai_create(transcript + overwrite_chars)
            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            # if re.search(r"\b(exit|quit)\b", transcript, re.I):
            #     print("Exiting..")
            #     break
            #
            # num_chars_printed = 0
            # yield
def openai_create(prompt):
    credential_path = "./adamtts-360502-dd4287183c47.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
    url = "https://api.openai.com/v1/completions"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer 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'
    }
    payload = json.dumps({
        "model": "text-davinci-003",
        "prompt": prompt,
        "temperature": 1,
        "max_tokens": 10
    })
    response = requests.request("POST", url, headers=headers, data=payload)
    print("result==={}".format(response.json()['choices'][0]['text'].strip()))
    # gtts = GTTS(filename='response.mp3')
    # gtts.generate_mp3(response.json()['choices'][0]['text'].strip())
    # gtts.play_voice()
    return response.json()['choices'][0]['text'].strip()

def speechtotext():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = "en-US"  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    porcupine = pvporcupine.create(
        access_key='i/qSJyQsdRUWTUGJg1S2uTHKC9U7AU1GxvQZo7Oc2hn6DJ39teyrWA==',
        library_path=pvporcupine.LIBRARY_PATH,
        model_path=pvporcupine.MODEL_PATH,
        keyword_paths=['Hi-adam_en_linux_v2_1_0.ppn'],
        sensitivities=[0.5])

    with MicrophoneStream(RATE, CHUNK) as stream:
        wake_generator = stream.wake_generator()
        audio_generator = stream.generator()
        # while True:
        #     # print('22')
        #     pcm = next(wake_generator)
        #     # print(pcm)
        #     result = porcupine.process(pcm)
        #     if result >= 0:
        #         print('Detected')
        #         break
        print('start')
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator
        )
        print('after requests')
        responses = client.streaming_recognize(streaming_config, requests)
        print('after responses')
        # Now, put the transcription responses to use.
        text = listen_print_loop(responses)


        # fun = listen_print_loop(responses)
        # # next(fun)
        # return fun


if __name__ == "__main__":
    speechtotext()
# [END speech_transcribe_streaming_mic]
