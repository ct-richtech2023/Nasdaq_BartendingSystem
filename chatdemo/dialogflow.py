#!/usr/bin/env python

# Copyright 2017 Google LLC
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

"""DialogFlow API Detect Intent Python sample with audio file.
Examples:
  python detect_intent_audio.py -h
  python detect_intent_audio.py --project-id PROJECT_ID \
  --session-id SESSION_ID --audio-file-path resources/book_a_room.wav
  python detect_intent_audio.py --project-id PROJECT_ID \
  --session-id SESSION_ID --audio-file-path resources/mountain_view.wav
  python detect_intent_audio.py --project-id PROJECT_ID \
  --session-id SESSION_ID --audio-file-path resources/today.wav
"""

import uuid

from google.cloud import dialogflow

from record import MyRecord


# credential_path = "F:\\documents\\keys\\applied-pursuit-352501-10d1ae34a22f.json"
# credential_path = "F:\\documents\\keys\\adamtalk-015ed8810228.json"
# credential_path = "./adamtts-360502-dd4287183c47.json"
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path

# [START dialogflow_detect_intent_audio]

class DialogFlow:
    def __init__(self, project_id='adamtts-360502', audio_path='request.mp3'):
        self.project_id = project_id
        self.audio_path = audio_path
        self.session_id = str(uuid.uuid4())

        self.session_client = dialogflow.SessionsClient()

    def detect_intent_audio(self, temp_file=None, language_code='en-US'):
        """Returns the result of detect intent with an audio file as input.
        Using the same `session_id` between requests allows continuation
        of the conversation."""

        # Note: hard coding audio_encoding and sample_rate_hertz for simplicity.
        audio_encoding = dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16
        sample_rate_hertz = 48000

        session = self.session_client.session_path(self.project_id, self.session_id)
        print("Session path: {}\n".format(session))

        if temp_file:
            filename = temp_file
        else:
            filename = self.audio_path
        with open(filename, "rb") as audio_file:
            input_audio = audio_file.read()

        audio_config = dialogflow.InputAudioConfig(
            audio_encoding=audio_encoding,
            language_code=language_code,
            sample_rate_hertz=sample_rate_hertz,
        )
        query_input = dialogflow.QueryInput(audio_config=audio_config)

        request = dialogflow.DetectIntentRequest(
            session=session, query_input=query_input, input_audio=input_audio,
        )
        response = self.session_client.detect_intent(request=request)

        print("=" * 20)
        print("Query text: {}".format(response.query_result.query_text))
        print(
            "Detected intent: {} (confidence: {})\n".format(
                response.query_result.intent.display_name,
                response.query_result.intent_detection_confidence,
            )
        )
        print("Fulfillment text: {}\n".format(response.query_result.fulfillment_text))
        return response.query_result.fulfillment_text

    def detect_intent_text(self, text, language_code='en'):
        print('question:  ', text)
        session = self.session_client.session_path(self.project_id, self.session_id)

        text_input = dialogflow.TextInput(text=text, language_code=language_code)

        query_input = dialogflow.QueryInput(text=text_input)
        # DetectIntentRequest
        audio_encoding = dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16
        sample_rate_hertz = 48000
        # output_config = dialogflow.OutputAudioConfig(audio_encoding=audio_encoding, sample_rate_hertz=sample_rate_hertz)

        # request = dialogflow.DetectIntentRequest(session=session, query_input=query_input, output_audio_config=output_config)
        request = dialogflow.DetectIntentRequest(session=session, query_input=query_input)

        response = self.session_client.detect_intent(request=request)
        # with open('diaout.mp3', "wb") as out:
        #     out.write(response.output_audio)
        #     print('Audio content written to file {}'.format('diaout.mp3'))
        # print('intentDetectionConfidence = {}'.format(response.query_result.intent_detection_confidence))
        if response.query_result.intent_detection_confidence >= 0.8:
            return response.query_result.fulfillment_text
        else:
            return 'pass'

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

    PROJECT_ID = 'adamtts-360502'
    # PROJECT_ID = 'applied-pursuit-352501'
    session_id = str(uuid.uuid4())
    AUDIO_PATH = 'hi.mp3'

    dia = DialogFlow(PROJECT_ID, AUDIO_PATH)

    response = dia.detect_intent_audio(
        PROJECT_ID, session_id, AUDIO_PATH
    )
