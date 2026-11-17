from fastapi import APIRouter, Body
from app.services import close_service as svc

router = APIRouter(prefix="/close", tags=["close"])


@router.get("/preview")
def preview(business_day: str | None = None):
    return svc.preview(business_day)


@router.post("/seal")
def seal(body: dict = Body(...)):
    return svc.seal(body)


@router.get("/batches")
def batches():
    return svc.list_batches()


@router.get("/variances")
def variances():
    return svc.list_variances()


@router.post("/batches/{batch_id}/void")
def void_batch(batch_id: int, body: dict = Body(default_factory=dict)):
    return svc.void_batch(batch_id, body)


@router.get("/precheck")
def precheck(business_day: str | None = None):
    return svc.seal_precheck({"business_day": business_day})


@router.get("/consistency")
def consistency(business_day: str | None = None):
    day = business_day
    if not day:
        from app.db import connect
        from app.repositories import settings as settings_repo
        conn = connect()
        try:
            day = settings_repo.get(conn, "business_day") or ""
        finally:
            conn.close()
    return svc.pinned_consistency(day)
