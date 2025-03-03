tools= [
    {
      "type": "function",
      "function": {
        "name": "deepresearch",
        "description": "Get a deep research on a topic",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "The query to perform the research on"
            }
          },
          "required": ["query"]
        }
      }
    }
]

