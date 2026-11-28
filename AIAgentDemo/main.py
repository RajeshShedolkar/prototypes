
import json

from openai import OpenAI
from dotenv import load_dotenv

from task_tools import add_task, list_tasks

load_dotenv()

client = OpenAI()


# 1. Define tools available to the AI Agent
tools = [
    {
        "type": "function",
        "name": "add_task",
        "description": "Add a new task with its title and due date.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The task title"
                },
                "due_date": {
                    "type": "string",
                    "description": "The task due date"
                }
            },
            "required": ["title", "due_date"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "list_tasks",
        "description": "Retrieve all saved tasks.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    }
]


# 2. Execute the selected Python function
def execute_tool(tool_name, arguments):

    if tool_name == "add_task":
        return add_task(**arguments)

    elif tool_name == "list_tasks":
        return list_tasks()

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


# 3. Run the AI Agent
def run_agent(user_input):

    response = client.responses.create(
        model="gpt-5.5",
        instructions="""
        You are a Personal Task Assistant.

        Your responsibilities:
        1. Understand user requests.
        2. Use add_task when the user wants to create a task.
        3. Use list_tasks when the user asks to see tasks.
        4. Do not claim a task was saved unless the tool succeeds.
        5. Give concise responses.
        """,
        input=user_input,
        tools=tools
    )

    # 4. Check whether the model requested a tool
    tool_calls = [
        item for item in response.output
        if item.type == "function_call"
    ]

    if not tool_calls:
        return response.output_text

    # 5. Execute requested tools
    tool_outputs = []

    for tool_call in tool_calls:

        arguments = json.loads(tool_call.arguments)

        result = execute_tool(
            tool_call.name,
            arguments
        )

        tool_outputs.append({
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": json.dumps(result)
        })

    # 6. Send tool results back to the model
    final_response = client.responses.create(
        model="gpt-5.5",
        instructions="Explain the tool results clearly to the user.",
        input=response.output + tool_outputs
    )

    return final_response.output_text


# 7. Main application
if __name__ == "__main__":

    print("Personal AI Agent Started!")
    print("Type 'exit' to quit.\n")

    while True:

        user_input = input("You: ")

        if user_input.lower() == "exit":
            break

        answer = run_agent(user_input)

        print("\nAgent:", answer)
        print("-" * 50)
