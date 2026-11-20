"""보고서 처리 Agent 애플리케이션 진입점. 실행: python -m app.main"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.db.session import get_session_factory
from app.services.errors import DomainError
from app.api import reports, search

app=FastAPI(title='Report Agent | 2026-11-20',version='1.0.0')

app.include_router(reports.router)

app.include_router(search.router)

@app.exception_handler(DomainError)
def on_domain_error(request:Request,exc:DomainError):
    return JSONResponse(status_code=exc.status,
      content={'error':{'code':exc.code,'message':exc.message,'details':{}}})

@app.get('/health',tags=['System'])
def health():
    try:
        with get_session_factory()() as db:
            db.execute(text('SELECT 1')).scalar_one()
            exists=db.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")).scalar_one()
            if not exists:raise RuntimeError('pgvector extension missing')
        return {'status':'ok','db':'ready','vector':'ready'}
    except Exception:
        return JSONResponse(status_code=503,
           content={'error':{'code':'DB_UNAVAILABLE','message':'DB 또는 pgvector를 확인하세요.','details':{}}})

def main():
    import uvicorn
    # 공통 main()은 완성. Core 구현은 app/api, services, repositories에 분리.
    uvicorn.run('app.main:app',host='127.0.0.1',port=8000,reload=False)

if __name__=='__main__':main()
