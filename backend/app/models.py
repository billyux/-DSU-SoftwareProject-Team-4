"""SQLAlchemy 테이블 정의 (DB 스키마 확정되면 이 파일을 채워나가면 됨)"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .db import Base


class Region(Base):
    """행정동 기준 지역 테이블"""
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # 예: "해운대동"
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    safety_score = relationship("SafetyScore", back_populates="region", uselist=False)
    facility_score = relationship("FacilityScore", back_populates="region", uselist=False)
    transit_score = relationship("TransitScore", back_populates="region", uselist=False)


class SafetyScore(Base):
    __tablename__ = "safety_scores"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), unique=True, nullable=False)
    score = Column(Float, nullable=False)  # 0~100 정규화된 점수

    region = relationship("Region", back_populates="safety_score")


class FacilityScore(Base):
    __tablename__ = "facility_scores"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), unique=True, nullable=False)
    score = Column(Float, nullable=False)

    region = relationship("Region", back_populates="facility_score")


class TransitScore(Base):
    __tablename__ = "transit_scores"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), unique=True, nullable=False)
    score = Column(Float, nullable=False)

    region = relationship("Region", back_populates="transit_score")


class Facility(Base):
    """위치 기반 시설 공통 테이블 (CCTV, 어린이집, 병원 등).

    행정동 단위로 집계하는 위 Score 테이블들과 달리, 지도 클릭 지점 기준
    반경 검색(예: 방범지도)에 쓰기 위해 개별 시설의 위도/경도를 그대로 저장한다.
    데이터셋마다 컬럼명이 달라도 data/scripts/clean_facilities.py에서
    이 스키마(category, facility_type, name, latitude, longitude)로 통일해서 적재한다.
    """
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)  # 지도 레이어 구분: "안전" | "생활편의" | "음식점" | "교통"
    # 세부 유형. 상가는 업종 소분류("편의점", "내과/소아과 의원" 등). 점수 가중치는
    # FacilityTypeWeight 테이블에서 이 값으로 찾는다(행에 가중치를 저장하지 않음)
    facility_type = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    source = Column(String, nullable=True)  # 원본 데이터셋명 (출처 추적용)
    # 원본 데이터의 고유번호(상가 bizesId, 병원 ykiho) — 관리자 즉시 최신화에서 같은 시설 판단용.
    # 최신화 대상이 아닌 데이터(버스정류장, CCTV, 지하철역, 학교, 노인교실)와 CSV로 막 적재한 행은 비어 있음
    external_id = Column(String, nullable=True, index=True)


class CategoryParam(Base):
    """점수 카테고리별 물리적 파라미터: 반경(r_c), 목표 개수(n_c).

    "몇 m 안이면 가깝다고 볼지", "몇 개면 충분하다고 볼지"는 페르소나(개인/가족/노인)에
    따라 값이 달라지는 중요도 판단이 아니라 거리·수량 기준이라, 페르소나 공통으로 둔다.
    '의료_종합병원'의 radius_m은 "가장 가까운 종합병원을 찾을 때 쓰는 검색 반경"으로 쓴다.
    """
    __tablename__ = "category_params"

    id = Column(Integer, primary_key=True, index=True)
    score_category = Column(String, unique=True, nullable=False, index=True)
    radius_m = Column(Float, nullable=False)  # r_c
    target_count = Column(Float, nullable=False)  # n_c ("이만큼 있으면 충분하다")


class PersonaCategoryWeight(Base):
    """페르소나(개인/가족/노인)별 카테고리 가중치(W_c).

    같은 "병원 접근성"이라도 페르소나마다 중요도가 다르다고 보고, AHP 설문 등으로
    페르소나별로 따로 정한다. '의료_의원급' 행의 값은 의료_종합병원과 합산한 '의료'
    전체 가중치를 뜻한다(계산 방식 문서 5단계 참고). '의료_종합병원' 행은 0으로 둔다.
    같은 페르소나 안에서 전체 합이 1이 되도록 맞춘다.
    """
    __tablename__ = "persona_category_weights"
    __table_args__ = (UniqueConstraint("persona", "score_category", name="uq_persona_category"),)

    id = Column(Integer, primary_key=True, index=True)
    persona = Column(String, nullable=False, index=True)  # "개인" | "가족" | "노인"
    score_category = Column(String, nullable=False, index=True)
    category_weight = Column(Float, nullable=False)  # W_c


class PersonaFacilityTypeWeight(Base):
    """페르소나별 시설 유형 가중치(wᵢ). 여기 없는 facility_type은 그 페르소나 점수에서 제외된다."""
    __tablename__ = "persona_facility_type_weights"
    __table_args__ = (UniqueConstraint("persona", "facility_type", name="uq_persona_facility_type"),)

    id = Column(Integer, primary_key=True, index=True)
    persona = Column(String, nullable=False, index=True)  # "개인" | "가족" | "노인"
    facility_type = Column(String, nullable=False, index=True)
    score_category = Column(String, nullable=False, index=True)  # CategoryParam.score_category 참조
    weight = Column(Float, nullable=False)
