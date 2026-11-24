"""관리자 '즉시 데이터 최신화'(FR-09).

공공 API로 다시 받을 수 있고 자주 바뀌는 시설(상가·병원)만 최신 데이터와 비교해서, 없어진 시설은 지우고
새로 생긴 시설은 추가하고, 이름·위치·유형이 바뀐 시설은 고친다. 버스정류장은 API는 있지만 거의 안 바뀌어서
제외했고, CCTV·지하철역·학교(파일 데이터)와 노인교실(사람이 정리한 데이터)은 API가 없어서 대상이 아니다.

같은 시설인지는 원본 고유번호(external_id: 상가 bizesId, 병원 ykiho)로 판단한다.
고유번호가 아직 없는 기존 행(CSV로 적재된 행의 첫 최신화)은 이름이 같고 MATCH_MAX_M 이내인 시설의
고유번호를 붙여서, 같은 시설이 "삭제 후 추가"로 처리되지 않게 한다.

작업이 수십 초~몇 분 걸려서 요청 안에서 돌리지 않고 백그라운드 스레드로 실행한다.
진행 상태는 이 프로세스 메모리에만 있어서 서버가 재시작되면 사라진다.
"""
import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone

import requests
from sqlalchemy import text

from ..db import SessionLocal
from ..models import Facility
from .facility_classification import STORE_CATEGORY_MAP, hospital_facility_type, store_facility_type
from .geo import haversine_distance_m

STORE_SOURCE = "소상공인시장진흥공단_상가업소정보"
HOSPITAL_SOURCE = "건강보험심사평가원_병원정보서비스"

MATCH_MAX_M = 100
# 새로 받은 건수가 기존의 절반도 안 되면 API 장애·부분 응답으로 보고 그 데이터는 지우지 않는다
MIN_KEEP_RATIO = 0.5
# 묶음 SQL 한 문장에 넣는 행 수 — SQLite 기본 파라미터 한도(999)를 넘지 않게 정함
UPDATE_CHUNK = 150  # 행당 파라미터 6개 (id는 정수라 SQL에 직접 넣음)
INSERT_CHUNK = 140  # 행당 파라미터 7개
DELETE_CHUNK = 500  # 파라미터 없음
REQUEST_TIMEOUT = 30

SASANG_SIGNGU_CD = "26530"  # 상가 API(행정표준코드)
HIRA_SIDO_CD = "210000"  # 심평원 자체 코드: 부산
HIRA_SGGU_CD = "210015"  # 심평원 자체 코드: 부산 사상구

UPDATABLE_FIELDS = ("category", "facility_type", "name", "latitude", "longitude")
UPDATE_COLUMNS = ("external_id",) + UPDATABLE_FIELDS
INSERT_COLUMNS = ("category", "facility_type", "name", "latitude", "longitude", "source", "external_id")


def _row(category, facility_type, name, lat, lng, source, external_id) -> dict:
    return {
        "category": category,
        "facility_type": facility_type,
        "name": name,
        "latitude": float(lat),
        "longitude": float(lng),
        "source": source,
        "external_id": str(external_id),
    }


# ---------- 원본 API 수집 ----------

def _fetch_stores(key: str) -> list[dict]:
    """소상공인 상가(상권)정보 — data/scripts/fetch_stores.py와 같은 API."""
    url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"
    items, page = [], 1
    while True:
        params = {"serviceKey": key, "divId": "signguCd", "key": SASANG_SIGNGU_CD,
                  "type": "json", "numOfRows": 1000, "pageNo": page}
        res = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        body = res.json()["body"]
        items.extend(body["items"])
        if len(items) >= body["totalCount"] or not body["items"]:
            break
        page += 1

    rows = []
    for it in items:
        mapping = STORE_CATEGORY_MAP.get(it["indsLclsNm"])
        if not mapping or not it.get("lat") or not it.get("lon"):
            continue
        rows.append(_row(mapping[0], store_facility_type(it["indsLclsNm"], it["indsSclsNm"]),
                         it["bizesNm"], it["lat"], it["lon"], STORE_SOURCE, it["bizesId"]))
    return rows


def _fetch_hospitals(key: str) -> list[dict]:
    """건강보험심사평가원 병원정보서비스 — 사상구 전체 의료기관."""
    url = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
    items, page = [], 1
    while True:
        params = {"serviceKey": key, "sidoCd": HIRA_SIDO_CD, "sgguCd": HIRA_SGGU_CD,
                  "numOfRows": 1000, "pageNo": page, "_type": "json"}
        res = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        body = res.json()["response"]["body"]
        page_items = (body.get("items") or {}).get("item") or []
        if isinstance(page_items, dict):  # 1건이면 리스트가 아니라 dict로 옴
            page_items = [page_items]
        items.extend(page_items)
        if len(items) >= body["totalCount"] or not page_items:
            break
        page += 1

    return [
        _row("생활편의", hospital_facility_type(it["clCdNm"], it["yadmNm"]), it["yadmNm"],
             it["YPos"], it["XPos"], HOSPITAL_SOURCE, it["ykiho"])
        for it in items
        if it.get("XPos") and it.get("YPos")
    ]


# ---------- 기존 DB와 비교해서 반영 ----------

def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _bulk_update(db, rows: list[tuple[int, dict]]):
    """여러 행을 CASE 문 하나로 한 번에 고친다 (Turso는 한 행씩 보내면 행마다 왕복이 생겨 느림).
    id는 DB에서 읽은 정수라 SQL에 그대로 넣고, 값은 모두 바인딩 파라미터로 넘긴다."""
    for chunk in _chunks(rows, UPDATE_CHUNK):
        params, sets = {}, []
        for col in UPDATE_COLUMNS:
            whens = []
            for n, (fid, values) in enumerate(chunk):
                key = f"{col}_{n}"
                params[key] = values[col]
                whens.append(f"WHEN {int(fid)} THEN :{key}")
            sets.append(f"{col} = CASE id {' '.join(whens)} END")
        ids = ", ".join(str(int(fid)) for fid, _ in chunk)
        db.execute(text(f"UPDATE facilities SET {', '.join(sets)} WHERE id IN ({ids})"), params)
        db.commit()


def _bulk_insert(db, rows: list[dict]):
    for chunk in _chunks(rows, INSERT_CHUNK):
        params, values = {}, []
        for n, r in enumerate(chunk):
            values.append("(" + ", ".join(f":{c}_{n}" for c in INSERT_COLUMNS) + ")")
            params.update({f"{c}_{n}": r[c] for c in INSERT_COLUMNS})
        db.execute(text(f"INSERT INTO facilities ({', '.join(INSERT_COLUMNS)}) VALUES {', '.join(values)}"), params)
        db.commit()


def _bulk_delete(db, ids: list[int]):
    for chunk in _chunks(ids, DELETE_CHUNK):
        db.execute(text(f"DELETE FROM facilities WHERE id IN ({', '.join(str(int(i)) for i in chunk)})"))
        db.commit()


def _sync_source(db, source: str, fresh: list[dict]) -> dict:
    """먼저 무엇을 추가·수정·삭제할지 계획을 세운 뒤, 묶음 SQL로 한꺼번에 반영한다."""
    existing = db.query(Facility).filter(Facility.source == source).all()
    if existing and len(fresh) < len(existing) * MIN_KEEP_RATIO:
        raise RuntimeError(
            f"새로 받은 데이터가 {len(fresh)}건으로 기존 {len(existing)}건의 절반도 안 됩니다. "
            "API 오류일 수 있어 이 데이터는 바꾸지 않았습니다."
        )

    fresh_by_id = {r["external_id"]: r for r in fresh}
    ext_of = {f.id: f.external_id for f in existing}  # 기존 행 id -> 고유번호 (아래에서 새로 붙이는 것 포함)
    by_ext = {ext: f for f in existing if (ext := f.external_id)}

    # 고유번호가 없는 기존 행: 이름이 같고 가장 가까운(MATCH_MAX_M 이내) 새 시설의 고유번호를 붙인다
    unclaimed_by_name = defaultdict(list)
    for ext, r in fresh_by_id.items():
        if ext not in by_ext:
            unclaimed_by_name[r["name"]].append(r)
    for f in existing:
        if f.external_id:
            continue
        candidates = [r for r in unclaimed_by_name.get(f.name, []) if r["external_id"] not in by_ext]
        best = min(
            candidates,
            key=lambda r: haversine_distance_m(f.latitude, f.longitude, r["latitude"], r["longitude"]),
            default=None,
        )
        if best and haversine_distance_m(f.latitude, f.longitude, best["latitude"], best["longitude"]) <= MATCH_MAX_M:
            ext_of[f.id] = best["external_id"]
            by_ext[best["external_id"]] = f

    to_insert, to_update, updated = [], [], 0
    for ext, r in fresh_by_id.items():
        f = by_ext.get(ext)
        if f is None:
            to_insert.append(r)
            continue
        fields_changed = any(getattr(f, field) != r[field] for field in UPDATABLE_FIELDS)
        if fields_changed or f.external_id != ext:  # 내용이 바뀌었거나 고유번호를 새로 붙이는 경우
            to_update.append((f.id, {"external_id": ext, **{field: r[field] for field in UPDATABLE_FIELDS}}))
        updated += fields_changed
    to_delete = [fid for fid, ext in ext_of.items() if ext not in fresh_by_id]

    _bulk_update(db, to_update)
    _bulk_insert(db, to_insert)
    _bulk_delete(db, to_delete)
    return {"total": len(fresh_by_id), "added": len(to_insert), "updated": updated, "removed": len(to_delete)}


# ---------- 백그라운드 작업 상태 ----------

SOURCES = [
    ("상가", STORE_SOURCE, _fetch_stores),
    ("병원", HOSPITAL_SOURCE, _fetch_hospitals),
]

# 완료 예상 시간: 직전 실행에 걸린 시간을 쓰고, 기록이 없으면(서버 재시작 후 첫 실행) 이 값을 쓴다.
# Turso 기준 첫 실행(기존 행 약 6,000개에 고유번호 붙이기) 추정치 약 30초에 여유를 둔 값
DEFAULT_ESTIMATE_SECONDS = 40

_lock = threading.Lock()
_state = {"status": "idle", "started_at": None, "finished_at": None, "estimated_seconds": None,
          "error": None, "results": {}}
_last_duration_seconds: float | None = None


def _safe_error(e: Exception) -> str:
    # requests 에러 메시지에는 serviceKey가 든 요청 URL이 그대로 들어가서, 상태 API로 키가 새지 않게 바꾼다
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return f"공공데이터 API 응답 오류 (HTTP {e.response.status_code})"
    if isinstance(e, requests.RequestException):
        return f"공공데이터 API 연결 실패 ({type(e).__name__})"
    if isinstance(e, (KeyError, ValueError)):
        return f"공공데이터 API 응답 형식이 예상과 다릅니다 ({type(e).__name__})"
    return str(e)


def get_status() -> dict:
    with _lock:
        return json.loads(json.dumps(_state))


def _set_result(label: str, result: dict):
    with _lock:
        _state["results"][label] = result


def start_refresh() -> bool:
    """이미 실행 중이면 False."""
    started = datetime.now(timezone.utc)
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update(status="running", started_at=started.isoformat(), finished_at=None, error=None,
                      estimated_seconds=round(_last_duration_seconds or DEFAULT_ESTIMATE_SECONDS),
                      results={label: {"status": "waiting"} for label, _, _ in SOURCES})
    threading.Thread(target=_run, args=(started,), daemon=True).start()
    return True


def _run(started: datetime):
    global _last_duration_seconds
    key = os.getenv("DATA_GO_KR_KEY")
    error = None
    if not key:
        error = "서버에 DATA_GO_KR_KEY(공공데이터포털 인증키)가 설정되지 않았습니다."
    else:
        for label, source, fetch in SOURCES:
            _set_result(label, {"status": "running"})
            db = SessionLocal()
            try:
                result = _sync_source(db, source, fetch(key))
                _set_result(label, {"status": "done", **result})
            except Exception as e:  # 한 데이터가 실패해도 나머지는 계속 진행
                db.rollback()
                _set_result(label, {"status": "error", "error": _safe_error(e)})
            finally:
                db.close()

    finished = datetime.now(timezone.utc)
    with _lock:
        _state.update(status="error" if error else "done", finished_at=finished.isoformat(), error=error)
        if not error:
            _last_duration_seconds = (finished - started).total_seconds()
