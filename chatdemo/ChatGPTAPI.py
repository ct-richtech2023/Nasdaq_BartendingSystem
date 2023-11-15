import os
import openai

os.environ['OPENAI_API_KEY'] = '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'
# openai.api_key = "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"
openai.api_key = os.getenv("OPENAI_API_KEY")


def openai_create(prompt):
    response = openai.Completion.create(
        model="text-davinci-001",
        prompt=prompt,
        max_tokens=7,
        temperature=0
    )
    return response.choices[0].text


if __name__ == '__main__':
    result = openai.Completion.create("Hi")
    print("result=={}".format(result))
