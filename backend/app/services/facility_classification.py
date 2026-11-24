"""시설 원본 데이터 -> facilities.category / facility_type 분류 규칙.

data/scripts/clean_facilities.py(CSV 정리)와 services/facility_refresh.py(관리자 즉시 최신화)가
같은 규칙을 쓰도록 여기 한 곳에 둔다. facility_type 이름은 가중치 테이블의 키라서 바꾸면
persona_facility_type_weights도 같이 바꿔야 한다.
"""

# 상가업소정보의 업종대분류명(indsLclsNm) -> (category, 대분류 facility_type).
# 매핑에 없는 대분류(수리·개인, 과학·기술, 교육, 부동산, 시설관리·임대, 숙박)는 제외.
STORE_CATEGORY_MAP = {
    "소매": ("생활편의", "소매"),
    "보건의료": ("생활편의", "보건의료"),
    "예술·스포츠": ("생활편의", "문화체육"),
    "음식": ("음식점", "음식점"),
}


def store_facility_type(lcls: str, scls: str) -> str:
    """상가 facility_type은 업종 소분류(편의점, 약국 등)를 쓴다. 단 보건의료는 HIRA 병원 데이터와
    겹쳐서 점수가 두 번 들어가지 않도록 대분류("보건의료") 그대로 둔다(가중치 표에 없음 -> 점수 제외)."""
    return STORE_CATEGORY_MAP[lcls][1] if lcls == "보건의료" else scls


# HIRA 병원정보의 종별 -> facility_type
HOSPITAL_TYPE_MAP = {"병원": "일반병원"}

# 의원은 종별만으로 진료과를 알 수 없어서 이름으로 판별 (위에서부터 먼저 맞는 것)
CLINIC_NAME_RULES = [
    (("내과", "소아", "가정의학"), "내과/소아과 의원"),
    (("피부", "비뇨"), "피부/비뇨기과 의원"),
    (("성형",), "성형외과 의원"),
    (("이비인후",), "이비인후과 의원"),
    (("안과",), "안과 의원"),
    (("산부인과", "여성의원"), "산부인과 의원"),
    (("정신", "신경과"), "신경/정신과 의원"),
    (("외과",), "외과 의원"),
]


def hospital_facility_type(kind: str, name: str) -> str:
    if kind != "의원":
        return HOSPITAL_TYPE_MAP.get(kind, kind)
    for keywords, facility_type in CLINIC_NAME_RULES:
        if any(k in name for k in keywords):
            return facility_type
    return "기타 의원"
