"""보고서 Router: Path/Query/JSON/HTTP Status와 Service 호출만 담당합니다."""

from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.report import ReportCreate, CategoryCode
from app.services import report_service
from app.core.config import at_least
from app.services.errors import DomainError

router=APIRouter(prefix='/api/v1',tags=['Reports & Categories'])

@router.get('/categories')
def categories(db:Session=Depends(get_db)):
    return report_service.categories(db)

@router.post('/reports',status_code=201)
def create_report(body:ReportCreate,db:Session=Depends(get_db)):
    return report_service.create_report(db,body)

@router.get('/reports')
def list_reports(title:str|None=None,limit:int=Query(20,ge=1,le=100),
                 offset:int=Query(0,ge=0),category_code:CategoryCode|None=None,
                 updated_after:datetime|None=None,db:Session=Depends(get_db)):
    if not at_least('intermediate') and (category_code is not None or updated_after is not None):
        raise DomainError(422,'VALIDATION_ERROR','추가 필터는 Intermediate 기능입니다.')
    return report_service.list_reports(db,title,limit,offset,category_code,updated_after)

@router.get('/reports/{report_id}')
def get_report(report_id:int=Path(ge=1),db:Session=Depends(get_db)):
    return report_service.get_report(db,report_id)
