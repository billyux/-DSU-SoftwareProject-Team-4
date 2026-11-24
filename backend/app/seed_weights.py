"""점수 계산 가중치 초기값을 DB에 심는 일회성 스크립트.

docs/동네 진단 서비스 정주여건 점수 계산 방식.md 의 '파라미터 초안' 표 그대로를 넣는다.
페르소나(개인/가족/노인)별 가중치는 아직 AHP 설문 결과가 없어서, 일단 세 페르소나 모두
같은 초안 값으로 심어둔다 — 나중에 결과가 나오면 관리자 페이지나 API로 페르소나별로
다르게 고치면 된다.
기본 가중치는 테이블이 비어 있을 때만 넣고, 페르소나 옵션(ensure_persona_options)은 없는 행만
추가한다 — 이미 운영 중인 DB에 여러 번 실행해도 기존 값은 바뀌지 않는다.

실행: python -m app.seed_weights
"""
from .db import Base, engine, SessionLocal
from .models import CategoryParam, PersonaCategoryWeight, PersonaFacilityTypeWeight

PERSONAS = ["개인", "가족", "노인"]

CATEGORY_PARAMS = [
    # score_category, radius_m(r_c), target_count(n_c)
    ("안전", 300, 4),
    ("의료_의원급", 500, 2),
    # 종합병원은 반경 안 개수가 아니라 최근접 거리로 계산하므로, radius_m은
    # "이 거리 안에서 가장 가까운 종합병원을 찾는다"는 검색 반경으로 씀. target_count는 미사용
    ("의료_종합병원", 5000, 0),
    ("생필품", 400, 3),
    ("버스", 400, 2),
    ("지하철", 800, 1),
]

# 페르소나별 카테고리 가중치(W_c). '의료_의원급'은 종합병원과 합산한 '의료' 전체 가중치를 뜻함.
# 아직 AHP 결과가 없어 세 페르소나 모두 문서의 초안 값과 동일 (합계 1.0)
CATEGORY_WEIGHTS = {
    "안전": 0.20,
    "의료_의원급": 0.25,
    "의료_종합병원": 0.0,
    "생필품": 0.20,
    "버스": 0.15,
    "지하철": 0.20,
}

FACILITY_TYPE_WEIGHTS = [
    # facility_type, score_category, weight(wᵢ)
    ("cctv", "안전", 1.0),
    ("내과/소아과 의원", "의료_의원급", 0.6),
    ("피부/비뇨기과 의원", "의료_의원급", 0.1),
    ("성형외과 의원", "의료_의원급", 0.1),
    ("종합병원", "의료_종합병원", 1.0),
    ("슈퍼마켓", "생필품", 1.0),
    ("편의점", "생필품", 1.0),
    ("약국", "생필품", 1.0),
    ("버스정류장", "버스", 1.0),
    ("지하철역", "지하철", 1.0),
]

# 페르소나 옵션: 특정 페르소나에서만 계산에 들어가는 카테고리 (계산 방식 문서의 '옵션' 카테고리).
# 반경·목표 개수·가중치는 문서의 옵션 초안(어린이집·노인복지시설: 500m, 2곳, 0.15)을 따름
OPTION_CATEGORY_PARAMS = [
    ("교육", 500, 2),
    ("노인복지", 500, 2),
]
OPTION_CATEGORY_WEIGHT = 0.15
PERSONA_OPTIONS = {
    "가족": {"교육": [("초등학교", 1.0), ("중학교", 1.0), ("고등학교", 1.0)]},
    "노인": {"노인복지": [("노인교실", 1.0)]},
}


def ensure_persona_options(db):
    """옵션 카테고리 행 중 없는 것만 추가한다. 관리자 화면에서 조정해둔 기존 값은 건드리지 않으므로
    이미 운영 중인 DB에 실행해도 안전하다. 옵션 카테고리를 그 페르소나에 처음 추가할 때만
    합이 1이 되도록 기존 W_c를 다시 나눈다(W_c' = W_c / ΣW, 계산 방식 문서 5단계)."""
    for score_category, r_c, n_c in OPTION_CATEGORY_PARAMS:
        if not db.query(CategoryParam).filter_by(score_category=score_category).first():
            db.add(CategoryParam(score_category=score_category, radius_m=r_c, target_count=n_c))
            print(f"CategoryParam '{score_category}' 추가")

    for persona, categories in PERSONA_OPTIONS.items():
        for score_category, type_weights in categories.items():
            existing = db.query(PersonaCategoryWeight).filter_by(persona=persona).all()
            if not any(w.score_category == score_category for w in existing):
                total = sum(w.category_weight for w in existing) + OPTION_CATEGORY_WEIGHT
                for w in existing:
                    w.category_weight = round(w.category_weight / total, 4)
                db.add(
                    PersonaCategoryWeight(
                        persona=persona,
                        score_category=score_category,
                        category_weight=round(OPTION_CATEGORY_WEIGHT / total, 4),
                    )
                )
                print(f"[{persona}] 카테고리 '{score_category}' 추가, 기존 W_c를 합 1이 되도록 조정")

            for facility_type, weight in type_weights:
                exists = (
                    db.query(PersonaFacilityTypeWeight)
                    .filter_by(persona=persona, facility_type=facility_type)
                    .first()
                )
                if not exists:
                    db.add(
                        PersonaFacilityTypeWeight(
                            persona=persona,
                            facility_type=facility_type,
                            score_category=score_category,
                            weight=weight,
                        )
                    )
                    print(f"[{persona}] 시설 유형 '{facility_type}' 추가")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(CategoryParam).count() == 0:
            for score_category, r_c, n_c in CATEGORY_PARAMS:
                db.add(CategoryParam(score_category=score_category, radius_m=r_c, target_count=n_c))
            print(f"CategoryParam {len(CATEGORY_PARAMS)}건 추가")
        else:
            print("CategoryParam 이미 데이터 있음, 건너뜀")

        if db.query(PersonaCategoryWeight).count() == 0:
            count = 0
            for persona in PERSONAS:
                for score_category, w_c in CATEGORY_WEIGHTS.items():
                    db.add(PersonaCategoryWeight(persona=persona, score_category=score_category, category_weight=w_c))
                    count += 1
            print(f"PersonaCategoryWeight {count}건 추가 ({len(PERSONAS)}개 페르소나 x {len(CATEGORY_WEIGHTS)}개 카테고리)")
        else:
            print("PersonaCategoryWeight 이미 데이터 있음, 건너뜀")

        if db.query(PersonaFacilityTypeWeight).count() == 0:
            count = 0
            for persona in PERSONAS:
                for facility_type, score_category, weight in FACILITY_TYPE_WEIGHTS:
                    db.add(
                        PersonaFacilityTypeWeight(
                            persona=persona,
                            facility_type=facility_type,
                            score_category=score_category,
                            weight=weight,
                        )
                    )
                    count += 1
            print(f"PersonaFacilityTypeWeight {count}건 추가 ({len(PERSONAS)}개 페르소나 x {len(FACILITY_TYPE_WEIGHTS)}개 유형)")
        else:
            print("PersonaFacilityTypeWeight 이미 데이터 있음, 건너뜀")

        db.flush()
        ensure_persona_options(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
