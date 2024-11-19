from fastapi import APIRouter

from app.constants import RESPONSE_404
from app.routers import TimedAPIRoute
from app.v3.device_registrations.rest import api_router as device_registrations_router
from app.v3.notifications.rest import api_router as notifications_router

api_router = APIRouter(
    prefix='/v3',
    tags=['v3 Endpoints'],
    responses={404: {'description': RESPONSE_404}},
    route_class=TimedAPIRoute,
)

api_router.include_router(device_registrations_router)
api_router.include_router(notifications_router)
