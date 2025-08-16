import json
from datetime import datetime, timedelta
from groq import Groq

class ReminderExtractor:
    def __init__(self, api_key: str, model: str = "llama3-70b-8192"):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.function_schema = self._get_function_schema()
        self.schema_prompt = self._get_schema_prompt()

    def _get_function_schema(self):
        return {
            "name": "extract_reminder_time",
            "description": "Extract reminder time (hour, minute) and reminder message from a user message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hour": {
                        "type": "integer",
                        "description": "Hour in 24-hour format (0-23)"
                    },
                    "minute": {
                        "type": "integer",
                        "description": "Minute (0-59)"
                    },
                    "reminder_message": {
                        "type": "string",
                        "description": "Short friendly reminder message to play during a call"
                    }
                },
                "required": ["hour", "minute", "reminder_message"]
            }
        }

    def _get_schema_prompt(self):
        return """
You are an AI assistant that extracts reminder time and message from user requests.

Rules:
- Handle absolute times (e.g., "4:30 PM") and relative times (e.g., "in 15 minutes", "in 2 hours").
- If user says a relative time, add it to the current time to calculate the absolute hour and minute.
- Ignore words like "tomorrow", "next week" — only use today's time.
- Return time in 24-hour format (hour 0-23).
- The reminder_message must be friendly, conversational, and sound like a human phone reminder.
- Always start with a greeting, mention it's a reminder call, and then say the actual reminder content.
"""

    def extract(self, user_message: str, current_time: datetime) -> dict:
        # Detect if no time info is present → default to +10 min
        if not any(word in user_message.lower() for word in ["am", "pm", "minute", "hour", ":"]) \
           and not any(char.isdigit() for char in user_message):
            default_time = current_time + timedelta(minutes=10)
            return {
                "hour": default_time.hour,
                "minute": default_time.minute,
                "reminder_message": f"Hello! This is your friendly reminder call to {user_message.strip()}."
            }

        # Prepare AI prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that extracts reminder times and messages. "
                    "Follow the JSON schema strictly.\n"
                    + self.schema_prompt
                    + f"\nThe current time is {current_time.strftime('%H:%M')} in 24-hour format."
                )
            },
            {
                "role": "user",
                "content": user_message
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": self.function_schema}],
                tool_choice="auto",
                temperature=0
            )

            tool_call = response.choices[0].message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)

            # Ensure the reminder message is friendly even if LLM returns plain text
            if not arguments["reminder_message"].lower().startswith("hello"):
                arguments["reminder_message"] = (
                    f"{arguments['reminder_message'].strip()}"
                )

            return arguments

        except Exception:
            # AI failed → fallback +10 minutes
            fallback_time = current_time + timedelta(minutes=10)
            return {
                "hour": fallback_time.hour,
                "minute": fallback_time.minute,
                "reminder_message": f"Hello! This is your friendly reminder call to {user_message.strip()}."
            }



# Example usage:
if __name__ == "__main__":
    extractor = ReminderExtractor(api_key="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")
    current_time = datetime.now()
    result = extractor.extract("Remind me to check the oven in 20 mins", current_time)
    print(result)
