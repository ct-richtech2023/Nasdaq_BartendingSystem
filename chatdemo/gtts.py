import time
import os

from google.cloud import texttospeech
from pydub import AudioSegment
from pydub.playback import _play_with_ffplay, play
# from porcupine_demo_mic import PorcupineDemo

credential_path = "./adamtts-360502-dd4287183c47.json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path

class GTTS:
    def __init__(self, filename):
        self.filename = filename
        self.tts_client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code='en-US', name='en-US-Wavenet-D',
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.89,
            pitch=0.80,
            volume_gain_db=16.0
        )

    def generate_mp3(self, text):
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = self.tts_client.synthesize_speech(
            input=synthesis_input, voice=self.voice, audio_config=self.audio_config
        )
        with open(self.filename, "wb") as out:
            out.write(response.audio_content)
            print('Audio content written to file {}'.format(self.filename))

    def play_voice(self, temp_file=None):
        if temp_file:
            filename = temp_file
        else:
            filename = self.filename
        print('play {}'.format(filename))
        voice = AudioSegment.from_mp3(filename)
        # _play_with_ffplay(voice)
        # print("music is start={}".format(time.time()))
        play(voice)

        # print("music is done={}".format(time.time()))


if __name__ == '__main__':
    gtts = GTTS(filename='wake_up.mp3')
    gtts.generate_mp3('Hello, how may I help you?')
