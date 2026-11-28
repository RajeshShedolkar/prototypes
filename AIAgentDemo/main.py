
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()


def ask_ai(user_input):
    response = client.responses.create(
        model="gpt-5.5",
        instructions="You are a helpful personal AI assistant. Give concise answers.",
        input=user_input
    )

    return response.output_text


if __name__ == "__main__":
    question = input("You: ")

    answer = ask_ai(question)

    print("\nAI:", answer)
