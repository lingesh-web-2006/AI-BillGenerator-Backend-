import json
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyDzL9J6NwSHkJnO7qC-d-n11qi91Bv7lHI")

SYSTEM_PROMPT = """You are an intelligent assistant for an employee billing system.
Your job is to parse natural language voice commands and extract structured billing information.

You MUST respond ONLY with a valid JSON object in this exact format:
{
    "employee_name": "<extracted full or partial employee name>",
    "action": "generate_bill",
    "notes": "<any optional notes mentioned, empty string if none>",
    "date": "<YYYY-MM-DD format, use today's date if not mentioned>"
}

Rules:
- Always set "action" to "generate_bill" if the command is about generating a bill or salary
- Extract the employee name exactly as spoken
- If no date is mentioned, use today's date
- Return ONLY the JSON object, no explanation, no markdown
"""

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Parse this voice command: Generate Arun bill",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0
        )
    )
    print("SUCCESS")
    print(response.text)
except Exception as e:
    print("ERROR:")
    print(str(e))
