from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from db import get_client, summarize_outcomes

app = FastAPI(title="QoG Dashboard")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    client = get_client()
    summary = client.get_dashboard_summary()
    contribution_split = client.get_contribution_split()
    decisions = client.get_decisions_with_outcomes(limit=20)
    people = client.get_people_with_stats()
    agents = client.get_agents_with_stats()
    
    outcomes = client.get_outcomes_for_summary()
    try:
        outcome_summary = summarize_outcomes(outcomes)
    except Exception as e:
        print(f"LLM summary error: {e}")
        outcome_summary = None
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "split": contribution_split,
            "decisions": decisions,
            "people": people,
            "agents": agents,
            "outcome_summary": outcome_summary,
        }
    )


def run():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
