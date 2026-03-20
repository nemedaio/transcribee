from fastapi import HTTPException, Request, status

from transcribee.services.auth import AuthenticatedUser


def require_admin(request: Request) -> AuthenticatedUser:
    current_user = request.app.state.auth_service.current_user(request)
    if current_user is None or not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
