"""관리자 '즉시 데이터 최신화'(FR-09) 엔드포인트.

DB의 시설을 지우고 추가하는 작업이라, 실행은 서버 환경변수 ADMIN_PASSWORD와 같은 암호를
X-Admin-Password 헤더로 보낸 요청만 허용한다. 진행 상태 조회에는 개수만 나와서 암호 없이 연다.
"""
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from ..services.facility_refresh import get_status, start_refresh

router = APIRouter(prefix="/api/admin/refresh", tags=["admin-refresh"])


def _require_admin(x_admin_password: str | None = Header(default=None)):
    expected = os.getenv("ADMIN_PASSWORD")
    if not expected:
        raise HTTPException(status_code=503, detail="서버에 ADMIN_PASSWORD가 설정되지 않아 최신화를 실행할 수 없습니다.")
    if not x_admin_password or not secrets.compare_digest(x_admin_password.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="관리자 암호가 올바르지 않습니다.")


@router.post("", status_code=202, dependencies=[Depends(_require_admin)])
def start():
    if not start_refresh():
        raise HTTPException(status_code=409, detail="이미 최신화가 진행 중입니다.")
    return get_status()


@router.get("/status")
def status():
    return get_status()
