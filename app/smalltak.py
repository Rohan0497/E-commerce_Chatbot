
from dotenv import load_dotenv
from groq import Groq
import os
load_dotenv()

groq_client = Groq()


def talk(query):
    prompt = f"""
    '''You are a helpful and friendly chatbot designed for small talk. You can answer questions about the weather, your name, your purpose, and more.
    Question : {query}
    

    """
    completion = groq_client.chat.completions.create(
    model= os.environ['GROQ_MODEL'],
        messages=[
            {
                "role": "user",
                "content": prompt
            }
            ],
        # temperature=1,
        # max_completion_tokens=1024,
        # top_p=1,
        # stream=True,
        # stop=None
    )
    return completion.choices[0].message.content