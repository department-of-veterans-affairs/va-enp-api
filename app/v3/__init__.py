from fastapi import APIRouter, Depends

from app.auth import JWTBearer
from app.constants import RESPONSE_404
from app.routers import TimedAPIRoute
from app.v3.device_registrations.rest import api_router as device_registrations_router
from app.v3.notifications.rest import api_router as notifications_router

api_router = APIRouter(
    dependencies=[Depends(JWTBearer())],
    prefix='/v3',
    responses={404: {'description': RESPONSE_404}},
    route_class=TimedAPIRoute,
    tags=['v3 Endpoints'],
)

api_router.include_router(device_registrations_router)
api_router.include_router(notifications_router)
