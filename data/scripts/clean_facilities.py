"""위치 기반 시설 데이터(CCTV, 어린이집, 병원 등) 공통 전처리 틀.

공공데이터포털 데이터셋마다 컬럼명이 제각각이라(위도/경도, LAT/LOT, Y좌표/X좌표 등),
이 파일에서 공통 스키마(category, facility_type, name, latitude, longitude, source)로
통일해서 data/processed/facilities.csv 에 누적 저장한다.

수정 전에 docs/시설데이터_세분화_및_가중치_변경사항.md 를 먼저 읽을 것
(상가 목록 유지 규칙, facility_type과 가중치 표의 관계, DB 반영 방법).

새 데이터셋을 추가하려면:
1. data/raw/ 에 원본 CSV를 둔다
2. standardize()로 컬럼명을 공통 스키마로 맞춘 DataFrame을 만든다
3. main()의 SOURCES 리스트에 그 처리 결과를 추가한다
"""
import sys
from pathlib import Path

import pandas as pd

# 분류 규칙은 백엔드의 관리자 즉시 최신화 기능과 공유한다
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from app.services.facility_classification import (  # noqa: E402
    STORE_CATEGORY_MAP,
    hospital_facility_type,
    store_facility_type,
)

RAW_DIR = Path(__file__).parent.parent / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "processed"
SCHEMA_COLUMNS = ["category", "facility_type", "name", "latitude", "longitude", "source"]

# 공공데이터에서 자주 쓰이는 위도/경도 컬럼명 별칭 (필요시 계속 추가)
LATITUDE_ALIASES = ["위도", "lat", "LAT", "Y좌표", "y좌표"]
LONGITUDE_ALIASES = ["경도", "lot", "LOT", "lng", "X좌표", "x좌표"]


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str:
    for alias in aliases:
        if alias in df.columns:
            return alias
    raise KeyError(f"다음 별칭 중 일치하는 컬럼을 찾지 못함: {aliases} (실제 컬럼: {list(df.columns)})")


def standardize(
    df: pd.DataFrame,
    category: str,
    facility_type: str,
    source: str,
    name_col: str | None = None,
    lat_col: str | None = None,
    lng_col: str | None = None,
) -> pd.DataFrame:
    """원본 DataFrame을 공통 스키마(category/facility_type/name/latitude/longitude/source)로 변환."""
    lat_col = lat_col or _find_column(df, LATITUDE_ALIASES)
    lng_col = lng_col or _find_column(df, LONGITUDE_ALIASES)

    result = pd.DataFrame({
        "category": category,
        "facility_type": facility_type,
        "name": df[name_col] if name_col else None,
        "latitude": pd.to_numeric(df[lat_col], errors="coerce"),
        "longitude": pd.to_numeric(df[lng_col], errors="coerce"),
        "source": source,
    })

    before = len(result)
    result = result.dropna(subset=["latitude", "longitude"])
    dropped = before - len(result)
    if dropped:
        print(f"  경고: 위도/경도 누락으로 {dropped}건 제외됨")

    return result


STORE_SOURCE = "소상공인시장진흥공단_상가업소정보"
STORE_MATCH_MAX_M = 100


def standardize_stores(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """상가업소정보는 indsLclsNm 값에 따라 category가 달라져서 별도 처리."""
    rows = []
    for _, row in df.iterrows():
        mapping = STORE_CATEGORY_MAP.get(row["indsLclsNm"])
        if not mapping:
            continue
        category, _ = mapping
        rows.append({
            "category": category,
            "facility_type": store_facility_type(row["indsLclsNm"], row["indsSclsNm"]),
            "name": row["bizesNm"],
            "latitude": row["lat"],
            "longitude": row["lon"],
            "source": source,
        })

    result = pd.DataFrame(rows)
    result["latitude"] = pd.to_numeric(result["latitude"], errors="coerce")
    result["longitude"] = pd.to_numeric(result["longitude"], errors="coerce")

    before = len(result)
    result = result.dropna(subset=["latitude", "longitude"])
    dropped = before - len(result)
    if dropped:
        print(f"  경고: 위도/경도 누락으로 {dropped}건 제외됨")

    return result


def attach_store_subtypes(stores: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """기존 상가 행(DB에 들어가 있는 목록)은 그대로 두고, 원본에서 같은 가게를 찾아 업종 소분류만 붙인다.
    원본을 나중에 다시 받으면 폐업·신규 가게가 섞여 있어서, 목록 자체를 원본으로 다시 만들면 DB와 달라진다.
    같은 가게 = 상호명이 같고 STORE_MATCH_MAX_M 이내. 못 찾은 가게는 기존 facility_type을 유지한다."""
    stores = stores.reset_index(drop=True)
    candidates = raw[raw["indsLclsNm"].isin(STORE_CATEGORY_MAP)][
        ["bizesNm", "lat", "lon", "indsLclsNm", "indsSclsNm"]
    ].copy()
    # 기존 행의 대분류(facility_type이 아직 대분류면 그 값)와 같은 대분류 안에서만 찾는다
    candidates["coarse"] = candidates["indsLclsNm"].map(lambda l: STORE_CATEGORY_MAP[l][1])
    lcls_by_scls = dict(zip(raw["indsSclsNm"], raw["indsLclsNm"]))
    coarse_values = {v[1] for v in STORE_CATEGORY_MAP.values()}
    stores_coarse = stores["facility_type"].map(
        lambda t: t if t in coarse_values else STORE_CATEGORY_MAP.get(lcls_by_scls.get(t), (None, None))[1]
    )
    merged = stores.assign(coarse=stores_coarse).reset_index().merge(
        candidates, left_on=["name", "coarse"], right_on=["bizesNm", "coarse"], how="inner"
    )
    # 사상구 범위에서는 평면 근사로 충분 (위도 1도 ≈ 111km, 경도 1도 ≈ 91km)
    merged["dist_m"] = (
        ((merged["latitude"] - merged["lat"]) * 111_000) ** 2
        + ((merged["longitude"] - merged["lon"]) * 91_000) ** 2
    ) ** 0.5
    merged = merged[merged["dist_m"] <= STORE_MATCH_MAX_M]
    best = merged.sort_values("dist_m").drop_duplicates("index").set_index("index")

    result = stores.copy()
    for i, row in best.iterrows():
        result.at[i, "facility_type"] = store_facility_type(row["indsLclsNm"], row["indsSclsNm"])
    print(f"  소분류 매칭: {len(best)}/{len(stores)}건 (못 찾은 {len(stores) - len(best)}건은 기존 분류 유지)")
    return result


def _reuse_processed(previous: pd.DataFrame | None, source: str, label: str) -> pd.DataFrame | None:
    """원본 CSV는 git에 안 올라가서 팀원 PC마다 없을 수 있다. 그때는 기존 facilities.csv에
    들어 있던 같은 출처의 행을 그대로 가져와서, 다른 데이터셋만 갱신해도 기존 데이터가 사라지지 않게 한다."""
    if previous is None:
        print(f"원본 파일 없음, 기존 처리 결과도 없음: {label} (건너뜀)")
        return None
    reused = previous.loc[previous["source"] == source, SCHEMA_COLUMNS]
    print(f"{label}: 원본 파일 없음 -> 기존 facilities.csv의 {len(reused)}건 재사용")
    return reused


def main():
    cctv_raw_path = RAW_DIR / "부산_방범용_CCTV_전체.csv"
    stores_raw_path = RAW_DIR / "사상구_상가업소정보.csv"
    subway_raw_path = RAW_DIR / "부산_도시철도역사정보.csv"
    bus_processed_path = PROCESSED_DIR / "사상구_버스정류소.csv"
    hospital_processed_path = PROCESSED_DIR / "사상구_병원정보.csv"
    senior_processed_path = PROCESSED_DIR / "사상구_노인교실.csv"
    school_raw_path = RAW_DIR / "한국교육시설안전원_초중등학교위치.csv"

    out_path = PROCESSED_DIR / "facilities.csv"
    previous = pd.read_csv(out_path, encoding="utf-8-sig") if out_path.exists() else None

    combined_parts = []

    if cctv_raw_path.exists():
        # 원본은 부산시 전체 데이터라 '구군' 컬럼으로 사상구만 필터링
        cctv_df = pd.read_csv(cctv_raw_path, encoding="cp949")
        cctv_df = cctv_df[cctv_df["구군"] == "사상구"]
        cctv_std = standardize(
            cctv_df,
            category="안전",
            facility_type="cctv",
            source="부산광역시_방범용 CCTV 정보_20251229",
            name_col="시설명칭",
        )
        combined_parts.append(cctv_std)
        print(f"CCTV: {len(cctv_std)}건")
    else:
        combined_parts.append(_reuse_processed(previous, "부산광역시_방범용 CCTV 정보_20251229", "CCTV"))

    existing_stores = (
        previous.loc[previous["source"] == STORE_SOURCE, SCHEMA_COLUMNS] if previous is not None else None
    )
    if existing_stores is not None and len(existing_stores):
        # 가게 목록은 기존 것(DB 기준)을 유지하고, 원본이 있으면 소분류만 갱신
        if stores_raw_path.exists():
            stores_df = pd.read_csv(stores_raw_path, encoding="utf-8-sig")
            existing_stores = attach_store_subtypes(existing_stores, stores_df)
        combined_parts.append(existing_stores)
        print(f"상가업소: {len(existing_stores)}건 (기존 목록 유지)")
    elif stores_raw_path.exists():
        stores_df = pd.read_csv(stores_raw_path, encoding="utf-8-sig")
        stores_std = standardize_stores(stores_df, source=STORE_SOURCE)
        combined_parts.append(stores_std)
        print(f"상가업소: {len(stores_std)}건 (업종 필터링 후)")
    else:
        print(f"원본 파일 없음: {stores_raw_path} (건너뜀, fetch_stores.py 먼저 실행)")

    if subway_raw_path.exists():
        # 공공데이터포털 다운로드 파일이 UTF-16 탭구분(TSV)으로 내려옴
        subway_df = pd.read_csv(subway_raw_path, encoding="utf-16", sep="\t")
        # 원본은 부산 전체 노선 데이터라 주소에 '사상구'가 들어간 역만 필터링
        subway_df = subway_df[subway_df["역사도로명주소"].str.contains("사상구", na=False)]
        subway_std = standardize(
            subway_df,
            category="교통",
            facility_type="지하철역",
            source="부산교통공사_도시철도역사정보_20210226",
            name_col="역사명",
            lat_col="역위도",
            lng_col="역경도",
        )
        combined_parts.append(subway_std)
        print(f"지하철역: {len(subway_std)}건")
    else:
        combined_parts.append(_reuse_processed(previous, "부산교통공사_도시철도역사정보_20210226", "지하철역"))

    if bus_processed_path.exists():
        # 팀원이 TAGO API + 사상구 행정동 경계 폴리곤으로 이미 정확하게 필터링해둔 결과
        # (data/scripts/collect_busstop_api.py 참고 — citycode는 행정구역과 안 맞아서
        # point-in-polygon 판정으로 거름)
        bus_df = pd.read_csv(bus_processed_path, encoding="utf-8-sig")
        bus_std = standardize(
            bus_df,
            category="교통",
            facility_type="버스정류장",
            source="국가대중교통정보센터(TAGO)_버스정류소정보",
            name_col="정류소명",
            lat_col="위도",
            lng_col="경도",
        )
        combined_parts.append(bus_std)
        print(f"버스정류장: {len(bus_std)}건 (사상구 행정동 경계 기준)")
    else:
        print(f"원본 파일 없음: {bus_processed_path} (건너뜀)")

    if hospital_processed_path.exists():
        # HIRA(건강보험심사평가원) 기반 공식 의료기관 목록. 상가업소정보의 "보건의료"
        # 카테고리(의원·한의원 등 사업자 등록 기준)와 일부 겹칠 수 있음 — 학기 프로젝트
        # 규모에서는 완전 중복 제거까지는 안 함. 대신 점수 계산에는 HIRA 쪽만 쓰도록
        # 상가 보건의료는 소분류를 붙이지 않는다(_store_type 참고)
        hospital_df = pd.read_csv(hospital_processed_path, encoding="utf-8-sig")
        hospital_std = standardize(
            hospital_df,
            category="생활편의",
            facility_type="",
            source="건강보험심사평가원_병원정보서비스",
            name_col="병원명",
        )
        # 종별 + 이름으로 진료과 구분 (종합병원, 내과/소아과 의원 등 — 가중치 표와 같은 이름)
        hospital_std["facility_type"] = [
            hospital_facility_type(kind, name)
            for kind, name in zip(hospital_df.loc[hospital_std.index, "종별"], hospital_std["name"])
        ]
        combined_parts.append(hospital_std)
        print(f"병원(HIRA): {len(hospital_std)}건")
    else:
        print(f"원본 파일 없음: {hospital_processed_path} (건너뜀)")

    if senior_processed_path.exists():
        # 공공데이터 없음 -> 사상구청 홈페이지(사람이 직접 확인) 목록을 카카오 지오코딩으로
        # 좌표 변환해둔 결과 (data/scripts/geocode_senior_classrooms.py). 휴관 시설 1곳 제외함.
        senior_df = pd.read_csv(senior_processed_path, encoding="utf-8-sig")
        senior_std = standardize(
            senior_df,
            category="생활편의",
            facility_type="노인교실",
            source="사상구청 홈페이지(수동 확인, 2026-11-05 기준)",
            name_col="name",
            lat_col="latitude",
            lng_col="longitude",
        )
        combined_parts.append(senior_std)
        print(f"노인교실: {len(senior_std)}건")
    else:
        print(f"원본 파일 없음: {senior_processed_path} (건너뜀)")

    if school_raw_path.exists():
        # 원본은 전국 데이터라 도로명주소에 '사상구'가 들어간 학교만 필터링.
        # 폐교/분교는 제외(운영상태="운영", 본교분교구분="본교"만 사용)
        school_df = pd.read_csv(school_raw_path, encoding="utf-8-sig")
        school_df = school_df[
            school_df["소재지도로명주소"].astype(str).str.contains("사상구", na=False)
            & (school_df["운영상태"] == "운영")
            & (school_df["본교분교구분"] == "본교")
        ]
        school_std = standardize(
            school_df,
            category="생활편의",
            facility_type="",
            source="한국교육시설안전원_초중등학교위치",
            name_col="학교명",
        )
        # 학교급(초등학교/중학교/고등학교)별로 facility_type 구분 — 가중치 표에서 이 이름으로 찾음
        school_std["facility_type"] = school_df.loc[school_std.index, "학교급구분"]
        combined_parts.append(school_std)
        print(f"학교: {len(school_std)}건")
    else:
        combined_parts.append(_reuse_processed(previous, "한국교육시설안전원_초중등학교위치", "학교"))

    combined_parts = [p for p in combined_parts if p is not None]
    if not combined_parts:
        print("처리할 데이터가 없습니다.")
        return

    combined = pd.concat(combined_parts, ignore_index=True)

    PROCESSED_DIR.mkdir(exist_ok=True)
    combined.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"완료: {len(combined)}건 저장됨 -> {out_path}")


if __name__ == "__main__":
    main()
