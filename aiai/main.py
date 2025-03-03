from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI
import json
from vars import tools
from deep import search
import os

app = FastAPI(title="AI loda lassan")

class ChatRequest(BaseModel):
    api_key: str
    base_url: str
    messages: List[Dict[str, str]]
    model: str
    temperature: float
    max_tokens: int
    tool_history: bool = True  # Default to True for backward compatibility

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    client = OpenAI(
        api_key=request.api_key,
        base_url=request.base_url
    )
    response = client.chat.completions.create(
        model=request.model,
        messages=request.messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    messages = request.messages.copy()
    messages.append(
        {
            "role": "assistant",
            "content": response.choices[0].message.content
        }
    )
    return messages

@app.post("/deepresearch")
async def deepresearch_endpoint(request: ChatRequest):
    print(f"Request: {request}")
    client = OpenAI(
        api_key=request.api_key,
        base_url=request.base_url
    )
    try:
        response = client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tool_choice={"type": "function", "function": {"name": "deepresearch"}},
            tools=tools,
        )
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        messages = request.messages.copy()
        # Create a version without tool responses for when tool_history is False
        messages_without = request.messages.copy()
        if tool_calls:
            print(f"Tool calls: {tool_calls}")
            # Add the model's response with the tool call to the complete history
            messages.append(response_message)
            for tool_call in tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                function_response = search(function_args.get("query"))
                print("Function response received")
                # Add tool response to the complete history
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "deepresearch",
                        "content": json.dumps(function_response),
                    }
                )
            # Get the final response from the model
            second_response = client.chat.completions.create(
                model=request.model,
                messages=messages
            )
            
            # Save the response content to a markdown file
            response_content = second_response.choices[0].message.content
            
            # Create a directory for markdown files if it doesn't exist
            os.makedirs("summary", exist_ok=True)
            
            # Generate a unique filename based on timestamp
            import time
            timestamp = int(time.time())
            filename = f"Summary/{timestamp}.md"
            
            # Write the content to the file, preserving newlines
            with open(filename, "w", encoding="utf-8") as f:
                f.write(response_content)
            
            final_response = {
                "role": "assistant",
                "content": response_content,
            }
            
            # Add the final response to both message versions
            messages.append(final_response)
            messages_without.append(final_response)
            
            # Return the appropriate version based on tool_history setting
            if request.tool_history:
                print(f"Tool history enabled. Markdown saved to {filename}")
                return messages
            else:
                print(f"Tool history disabled. Markdown saved to {filename}")
                return messages_without
                
        return {"error": "No tool calls were made"}
    except Exception as e:
        return {"error": f"Deep research failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)