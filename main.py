from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from db import get_client

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
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": summary,
            "split": contribution_split,
            "decisions": decisions,
            "people": people,
            "agents": agents,
        }
    )


def run():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
