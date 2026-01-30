import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _client


def summarize_outcomes(outcomes: list[dict]) -> str:
    if not outcomes:
        return "No outcomes to summarize."
    
    outcomes_text = "\n".join([
        f"- {o.get('outcome', 'Unknown outcome')}: {o.get('description', 'No description')} "
        f"(from decisions: {', '.join(filter(None, o.get('decisions', []))) or 'unknown'})"
        for o in outcomes
    ])
    
    client = get_openai_client()
    
    response = client.chat.completions.create(
        model="openai/gpt-4.1-nano",
        messages=[
            {
                "role": "system",
                "content": "You are an analyst summarizing decision outcomes. Be concise and insightful. Focus on patterns and key takeaways. Keep your response to 2-3 sentences."
            },
            {
                "role": "user", 
                "content": f"Summarize these outcomes from recent decisions:\n\n{outcomes_text}"
            }
        ],
        max_tokens=150,
    )
    
    return response.choices[0].message.content or "Unable to generate summary."
