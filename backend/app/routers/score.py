"""점수 조회 관련 엔드포인트"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import ScoreResponse
from ..services.geocoding import geocode
from ..services.neighborhood_score import DEFAULT_PERSONA, calculate_score

router = APIRouter(prefix="/api", tags=["score"])


# 사용자 검색 반경 — 생략하면 카테고리별 기본 반경으로 계산
RADIUS_QUERY = Query(default=None, gt=0, le=5000, description="검색 반경(m). 종합병원을 뺀 모든 카테고리에 적용")


@router.get("/score", response_model=ScoreResponse)
def get_score(
    address: str,
    persona: str = DEFAULT_PERSONA,
    radius_m: float | None = RADIUS_QUERY,
    db: Session = Depends(get_db),
):
    """주소를 받아 해당 지점의 정주여건 점수를 반환.

    흐름: 주소 → 좌표(지오코딩) → 반경 내 시설 조회 → 유형 가중치 × 거리 감쇠 →
    카테고리별 포화 점수 → 가중합. 공식은 docs/동네 진단 서비스 정주여건 점수 계산 방식.md 참고.
    persona: "개인" | "가족" | "노인" — 카테고리·시설 유형 가중치가 페르소나별로 다름.
    """
    try:
        lat, lng = geocode(address)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return get_score_by_point(lat=lat, lng=lng, persona=persona, radius_m=radius_m, db=db)


@router.get("/score/point", response_model=ScoreResponse)
def get_score_by_point(
    lat: float,
    lng: float,
    persona: str = DEFAULT_PERSONA,
    radius_m: float | None = RADIUS_QUERY,
    db: Session = Depends(get_db),
):
    """좌표를 직접 받아 점수를 반환 (지도 클릭 등 지오코딩이 필요 없는 경우)."""
    result = calculate_score(lat, lng, db, persona=persona, radius_m=radius_m)
    return ScoreResponse(
        total_score=result.total_score,
        categories=result.categories,
    )
