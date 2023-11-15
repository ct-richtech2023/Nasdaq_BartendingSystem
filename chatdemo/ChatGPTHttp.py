import os
import requests
import json
from gtts import GTTS

credential_path = "./adamtts-360502-dd4287183c47.json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
url = "https://api.openai.com/v1/completions"

headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer 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'
}


def openai_create(prompt):
    payload = json.dumps({
        "model": "text-davinci-003",
        "prompt": prompt,
        "temperature": 1,
        "max_tokens": 10
    })
    response = requests.request("POST", url, headers=headers, data=payload)
    print("result==={}".format(response.json()['choices'][0]['text'].strip()))
    gtts = GTTS(filename='response.mp3')
    gtts.generate_mp3(response.json()['choices'][0]['text'].strip())
    gtts.play_voice()
    return response.json()['choices'][0]['text'].strip()


if __name__ == '__main__':

    openai_create("Hi")
