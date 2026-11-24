"""Pydantic 요청/응답 모델 — API가 주고받는 데이터의 '모양'을 검증"""
from pydantic import BaseModel


class NearbyFacilityOut(BaseModel):
    name: str | None
    facility_type: str
    category: str  # 지도 색 구분용 (facilities.category)
    latitude: float
    longitude: float
    distance_m: float


class CategoryScoreOut(BaseModel):
    score_category: str
    score: float  # S_c (0~1)
    category_weight: float  # W_c
    nearby: list[NearbyFacilityOut]

    class Config:
        from_attributes = True


class ScoreResponse(BaseModel):
    total_score: float  # T (0~100)
    categories: list[CategoryScoreOut]


class PersonaFacilityTypeWeightOut(BaseModel):
    id: int
    persona: str
    facility_type: str
    score_category: str
    weight: float

    class Config:
        from_attributes = True


class FacilityTypeWeightUpdate(BaseModel):
    weight: float


class PersonaCategoryWeightOut(BaseModel):
    id: int
    persona: str
    score_category: str
    category_weight: float

    class Config:
        from_attributes = True


class CategoryWeightUpdate(BaseModel):
    category_weight: float


class CategoryParamOut(BaseModel):
    id: int
    score_category: str
    radius_m: float
    target_count: float

    class Config:
        from_attributes = True


class CategoryParamUpdate(BaseModel):
    radius_m: float | None = None
    target_count: float | None = None


class FacilityOut(BaseModel):
    name: str | None
    category: str
    facility_type: str
    latitude: float
    longitude: float
    distance_m: float

    class Config:
        from_attributes = True


class NearbyFacilitiesResponse(BaseModel):
    count: int
    facilities: list[FacilityOut]
