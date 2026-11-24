"""지점(위도/경도) 기준 정주여건 점수 계산 엔진.

docs/동네 진단 서비스 정주여건 점수 계산 방식.md 의 공식을 그대로 구현한다.
가중치(FacilityTypeWeight)와 카테고리 파라미터(CategoryParam)는 DB에서 읽어오므로,
관리자 페이지에서 값을 바꾸면 재배포 없이 바로 반영된다.
"""
import math
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import CategoryParam, Facility, PersonaCategoryWeight, PersonaFacilityTypeWeight
from .geo import haversine_distance_m

DEFAULT_PERSONA = "개인"

MEDICAL_CLINIC = "의료_의원급"
MEDICAL_HOSPITAL = "의료_종합병원"

# 종합병원 최근접 거리 점수 공식(계산 방식 문서 4단계)의 구간 — 데이터 자체에 근거한 상수라
# 카테고리 파라미터처럼 관리자가 바꿀 성격이 아니라서 코드에 고정해둠
HOSPITAL_FULL_SCORE_DISTANCE_M = 1000
HOSPITAL_ZERO_SCORE_DISTANCE_M = 5000


@dataclass
class CategoryBreakdown:
    score_category: str
    score: float  # S_c (0~1)
    category_weight: float  # W_c (의료_종합병원은 0, 의원급에 합산됨)
    nearby: list[dict] = field(default_factory=list)  # [{name, facility_type, distance_m}]


@dataclass
class ScoreResult:
    total_score: float  # T (0~100)
    categories: list[CategoryBreakdown]


def _bbox_candidates(db: Session, facility_types: list[str], lat: float, lng: float, radius_m: float) -> list[Facility]:
    """정확한 하버사인 계산 전에, 위경도 사각형으로 후보를 먼저 좁혀서 DB 조회량을 줄인다."""
    if not facility_types:
        return []
    d_lat = radius_m / 111_320
    d_lng = radius_m / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    return (
        db.query(Facility)
        .filter(Facility.facility_type.in_(facility_types))
        .filter(Facility.latitude.between(lat - d_lat, lat + d_lat))
        .filter(Facility.longitude.between(lng - d_lng, lng + d_lng))
        .all()
    )


def _nearby_with_distance(candidates: list[Facility], lat: float, lng: float, radius_m: float) -> list[tuple[Facility, float]]:
    result = []
    for f in candidates:
        d = haversine_distance_m(lat, lng, f.latitude, f.longitude)
        if d <= radius_m:
            result.append((f, d))
    return result


def _saturation_score(x: float, target_count: float) -> float:
    """S_c = 1 - e^(-X/k), k = n_c/6. n_c가 0이면(해당 없는 카테고리) 0을 돌려줌."""
    if target_count <= 0:
        return 0.0
    k = target_count / 6
    return 1 - math.exp(-x / k)


def _hospital_distance_score(d_min: float | None) -> float:
    """종합병원 최근접 거리 점수 (계산 방식 문서 4단계 공식)."""
    if d_min is None:
        return 0.0
    if d_min <= HOSPITAL_FULL_SCORE_DISTANCE_M:
        return 1.0
    if d_min >= HOSPITAL_ZERO_SCORE_DISTANCE_M:
        return 0.0
    return (HOSPITAL_ZERO_SCORE_DISTANCE_M - d_min) / (HOSPITAL_ZERO_SCORE_DISTANCE_M - HOSPITAL_FULL_SCORE_DISTANCE_M)


def _nearby_out(nearby: list[tuple[Facility, float]]) -> list[dict]:
    return sorted(
        [
            {
                "name": f.name,
                "facility_type": f.facility_type,
                "category": f.category,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "distance_m": round(d, 1),
            }
            for f, d in nearby
        ],
        key=lambda x: x["distance_m"],
    )


def calculate_score(
    lat: float, lng: float, db: Session, persona: str = DEFAULT_PERSONA, radius_m: float | None = None
) -> ScoreResult:
    """persona: "개인" | "가족" | "노인" — 카테고리·시설 유형 가중치가 페르소나별로 다르게 적용됨.

    radius_m: 사용자가 고른 검색 반경. 주면 종합병원을 뺀 모든 카테고리를 이 반경 안의 시설로 계산한다.
    종합병원은 반경 안에 없는 게 보통이라 문서 4단계대로 CategoryParam의 검색 반경(5km)에서 최근접 거리로 계산.
    안 주면 카테고리별 기본 반경(CategoryParam.radius_m)을 쓴다.
    """
    params = {p.score_category: p for p in db.query(CategoryParam).all()}
    category_weights = {
        w.score_category: w.category_weight
        for w in db.query(PersonaCategoryWeight).filter(PersonaCategoryWeight.persona == persona).all()
    }
    weights = db.query(PersonaFacilityTypeWeight).filter(PersonaFacilityTypeWeight.persona == persona).all()

    types_by_category: dict[str, list[PersonaFacilityTypeWeight]] = {}
    for w in weights:
        types_by_category.setdefault(w.score_category, []).append(w)

    breakdowns: dict[str, CategoryBreakdown] = {}

    for score_category, param in params.items():
        type_weights = types_by_category.get(score_category, [])
        facility_types = [tw.facility_type for tw in type_weights]
        weight_by_type = {tw.facility_type: tw.weight for tw in type_weights}

        if score_category == MEDICAL_HOSPITAL:
            # 종합병원: 개수가 아니라 가장 가까운 곳까지의 거리로 계산
            candidates = _bbox_candidates(db, facility_types, lat, lng, param.radius_m)
            nearby = _nearby_with_distance(candidates, lat, lng, param.radius_m)
            d_min = min((d for _, d in nearby), default=None)
            score = _hospital_distance_score(d_min)
            nearby_out = _nearby_out(nearby)[:5]
        else:
            radius = radius_m if radius_m is not None else param.radius_m
            candidates = _bbox_candidates(db, facility_types, lat, lng, radius)
            nearby = _nearby_with_distance(candidates, lat, lng, radius)
            x_c = sum(weight_by_type.get(f.facility_type, 0.0) * max(0.0, 1 - d / radius) for f, d in nearby)
            score = _saturation_score(x_c, param.target_count)
            nearby_out = _nearby_out(nearby)

        breakdowns[score_category] = CategoryBreakdown(
            score_category=score_category,
            score=round(score, 3),
            category_weight=category_weights.get(score_category, 0.0),
            nearby=nearby_out,
        )

    # 의료 = 의원급 50% + 종합병원 50% (계산 방식 문서 4단계). 의원급 category_weight(W_c)를
    # "의료 전체" 가중치로 보고 최종 합산에 그대로 씀
    if MEDICAL_CLINIC in breakdowns and MEDICAL_HOSPITAL in breakdowns:
        clinic = breakdowns[MEDICAL_CLINIC]
        hospital = breakdowns[MEDICAL_HOSPITAL]
        medical_score = 0.5 * clinic.score + 0.5 * hospital.score
    else:
        medical_score = 0.0

    total_weighted = 0.0
    for score_category, b in breakdowns.items():
        if score_category == MEDICAL_HOSPITAL:
            continue  # 의원급 가중치에 이미 합산됨
        if score_category == MEDICAL_CLINIC:
            total_weighted += b.category_weight * medical_score
        else:
            total_weighted += b.category_weight * b.score

    # P(사고 장소 감점)는 아직 데이터가 없어 0으로 고정 — 데이터 추가되면 여기에 반영
    accident_penalty = 0.0
    total_score = round(100 * total_weighted * (1 - 0.2 * accident_penalty), 1)

    return ScoreResult(total_score=total_score, categories=list(breakdowns.values()))
