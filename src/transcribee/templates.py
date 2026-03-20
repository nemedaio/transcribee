from fastapi import Request
from fastapi.templating import Jinja2Templates


def template_context(request: Request) -> dict:
    return {
        "app_name": request.app.state.settings.app_name,
        "auth_enabled": request.app.state.settings.auth_enabled,
        "current_user": getattr(request.state, "current_user", None),
    }


templates = Jinja2Templates(
    directory="src/transcribee/templates",
    context_processors=[template_context],
)
