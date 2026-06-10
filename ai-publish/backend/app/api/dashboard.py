from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = DashboardService(db)
    return service.get_summary()
