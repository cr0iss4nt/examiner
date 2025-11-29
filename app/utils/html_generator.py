from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="app/templates")

def render_test_page(request: Request, json_data):
    return templates.TemplateResponse(
        "test_template.html",
        {
            "request": request,
            "questions": json_data
        }
    )
