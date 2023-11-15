import requests

url = "https://texttospeech.googleapis.com/v1/text:synthesize"

bearer = 'ya29.c.b0AXv0zTMXat_5JC_ge98yNnmdpHsz35FYrG6hzFhojjczD0-s9MRhZWYAiaoPwI6GcmYZpYWh0mhTUJ1jTgx_2S_E_Yn61x3h2Oh6VoU9m1YjBvPxrp-ndhkcvQzJQP5mn_IM9b1wTSG51wXt4XIjI-H4Eo8apj1xyNXTVF9vfDZMM-3Swige8eDiZW2-_6rRJ_g1HawFE31vcI8IX7Vcsgfpso7ea34........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................'

headers = {'Authorization': 'Bearer {}'.format(bearer), 'Content-Type': 'application/json'}

data = {
    "input": {
        "text": "Android is a mobile operating system developed by Google, based on the Linux kernel and designed primarily for touchscreen mobile devices such as smartphones and tablets."
    },
    "voice": {
        "languageCode": "en-gb",
        "name": "en-GB-Standard-A",
        "ssmlGender": "FEMALE"
    },
    "audioConfig": {
        "audioEncoding": "MP3"
    }
}

res = requests.post(url, headers=headers, data=data)
print(res.status_code)
print(res.content)
