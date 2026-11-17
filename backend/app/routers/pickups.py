from fastapi import APIRouter, Body
from app.services import pickup_service as svc

router = APIRouter(prefix="/pickups", tags=["pickups"])


@router.get("")
def list_pickups(business_day: str | None = None):
    return svc.list_pickups(business_day)


@router.post("")
def create_pickup(body: dict = Body(...)):
    return svc.create_pickup(body)


@router.delete("/{pickup_id}")
def delete_pickup(pickup_id: int):
    return svc.remove_pickup(pickup_id)
