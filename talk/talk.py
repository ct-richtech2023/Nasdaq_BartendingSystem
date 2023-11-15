import os

from dialogflow import DialogFlow
from gtts import GTTS
from record import MyRecord
from collections import deque

credential_path = "./adamtts-360502-dd4287183c47.json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path

def start_talk():
    request_record = MyRecord(filename='request.mp3', threshold=10000)
    dia = DialogFlow(audio_path='request.mp3')
    gtts = GTTS(filename='response.mp3')

    count = 0

    # request_record.record(5)

    # first say hi
    text = dia.detect_intent_audio(temp_file='output.mp3')
    gtts.generate_mp3(text)
    gtts.play_voice()

    while True:
        request_record.record()
        text = dia.detect_intent_audio()
        if text == '':
            count += 1
        else:
            count = 0
            gtts.generate_mp3(text)
            gtts.play_voice()
        if count > 3:
            # gtts.play_voice(temp_file='bye.mp3')
            break

if __name__ == '__main__':
    start_talk()
