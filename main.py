from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="QoG Dashboard")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    metrics = {
        "ai_decisions": {"value": 847, "change": "+12%"},
        "time_saved": {"value": "34 min", "change": "+8%"},
        "quality_score": {"value": "78%", "change": "+5%"},
    }
    
    value_areas = [
        {"name": "Research & Analysis", "ai": 55, "human": 45, "warning": False},
        {"name": "Content Drafting", "ai": 55, "human": 45, "warning": False},
        {"name": "Strategic Planning", "ai": 50, "human": 50, "warning": True},
    ]
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "value_areas": value_areas,
            "member_count": 12,
        }
    )


def run():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
