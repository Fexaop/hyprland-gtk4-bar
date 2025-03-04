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

report_schema = {
    "type": "object",
    "properties": {
        "[THINK] [/THINK]": {"type": "string"},
        "MARKDOWN PHD LEVEL REPORT": {"type": "string"},
        "CONCLUSION": {"type": "string"},
    },
    "required": ["title", "director", "year"],
    "additionalProperties": False
}

from pydantic import BaseModel, Field


class ReportAnswer(BaseModel):
    think: str = Field(..., alias="[THINK] [/THINK]")
    report_content: str = Field(..., alias="MARKDOWN PHD LEVEL REPORT")
    conclusion: str = Field(..., alias="CONCLUSION")
