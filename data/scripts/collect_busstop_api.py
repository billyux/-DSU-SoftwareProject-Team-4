"""TAGO 버스정류소정보 API를 격자 좌표로 반복 호출해서 사상구 전체 정류소를 수집.

이 API(getCrdntPrxmtSttnList)는 "좌표 기준 반경 500m 내 정류소"만 조회 가능하고
구 전체를 한 번에 주는 기능이 없다. 그래서 사상구를 500m 간격 격자로 쪼개서
점마다 반복 호출한 뒤, 겹치는 부분에서 중복으로 잡힌 정류소를 nodeid 기준으로 제거한다.

격자 범위는 data/sasang_boundary.json(사상구 실제 행정동 경계, vuski/admdongkor
ver20250101에서 sgg=26530만 추출한 것)의 bbox + 반경(500m)만큼 여유를 둔다.

수집 결과는 도시코드(citycode)로 거르면 안 된다 — 직접 확인해보니 같은 citycode(38070)가
사상구 안/밖 정류소에 둘 다 쓰이고 있어서, 행정구역이 아니라 다른 기준(버스 운영사 등)으로
보인다. 그래서 citycode 대신 실제 좌표가 사상구 폴리곤 안에 있는지(point-in-polygon)로
최종 필터링한다.
"""
import json
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / "backend" / ".env")
API_KEY = os.getenv("DATA_GO_KR_KEY")

URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"
DATA_DIR = Path(__file__).parent.parent
PROCESSED_DIR = DATA_DIR / "processed"
BOUNDARY_PATH = DATA_DIR / "sasang_boundary.json"

RADIUS_DEG_LAT = 0.0045   # 약 500m
RADIUS_DEG_LON = 0.0055   # 약 500m (위도 35도 기준)
GRID_STEP_LAT = 0.0063    # 약 700m, 반경 500m 원이 안 겹치는 구간 없이 덮도록
GRID_STEP_LON = 0.0077


def load_boundary():
    return json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))


def boundary_bbox(boundary):
    lons, lats = [], []
    for f in boundary["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for lon, lat in poly[0]:
                lons.append(lon)
                lats.append(lat)
    return min(lons), max(lons), min(lats), max(lats)


def point_in_ring(x, y, ring):
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_boundary(lon, lat, boundary):
    for f in boundary["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            if point_in_ring(lon, lat, poly[0]):
                return True
    return False


def generate_grid(lon_min, lon_max, lat_min, lat_max):
    points = []
    lat = lat_min - RADIUS_DEG_LAT
    while lat <= lat_max + RADIUS_DEG_LAT:
        lon = lon_min - RADIUS_DEG_LON
        while lon <= lon_max + RADIUS_DEG_LON:
            points.append((round(lat, 6), round(lon, 6)))
            lon += GRID_STEP_LON
        lat += GRID_STEP_LAT
    return points


def main():
    boundary = load_boundary()
    lon_min, lon_max, lat_min, lat_max = boundary_bbox(boundary)
    grid = generate_grid(lon_min, lon_max, lat_min, lat_max)
    print(f"격자 점 개수: {len(grid)}개")

    all_items = {}  # nodeid -> row (딕셔너리 키로 중복 자동 제거)

    for i, (lat, lon) in enumerate(grid, start=1):
        params = {
            "serviceKey": API_KEY,
            "citycode": "21",
            "gpsLati": lat,
            "gpsLong": lon,
            "numOfRows": 100,
            "pageNo": 1,
            "_type": "json",
        }
        response = requests.get(URL, params=params)
        try:
            body = response.json()["response"]["body"]
            items = body.get("items") if isinstance(body, dict) else None
        except Exception as e:
            print(f"  [{i}번째 {lat},{lon}] 응답 처리 실패: {e} / raw: {response.text[:200]}")
            continue

        if items:
            item_list = items["item"]
            if isinstance(item_list, dict):  # 결과가 1건이면 리스트가 아니라 dict로 옴
                item_list = [item_list]
            for it in item_list:
                all_items[it["nodeid"]] = it

        if i % 20 == 0 or i == len(grid):
            print(f"{i}/{len(grid)}번째 격자점 처리, 누적 정류소(필터 전) {len(all_items)}개")

    # citycode로는 안 거르고, 실제 사상구 폴리곤 안에 있는지로만 최종 필터링
    filtered = [
        it for it in all_items.values()
        if point_in_boundary(it["gpslong"], it["gpslati"], boundary)
    ]
    print(f"폴리곤 필터링: {len(all_items)}개 -> {len(filtered)}개")

    df = pd.DataFrame(filtered)
    df = df.rename(columns={
        "nodeid": "정류소ID",
        "nodenm": "정류소명",
        "nodeno": "정류소번호",
        "gpslati": "위도",
        "gpslong": "경도",
        "citycode": "도시코드",
    })

    PROCESSED_DIR.mkdir(exist_ok=True)
    out_path = PROCESSED_DIR / "사상구_버스정류소.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"완료: {len(df)}개 정류소 저장 -> {out_path}")


if __name__ == "__main__":
    main()
