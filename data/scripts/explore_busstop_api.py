"""TAGO 버스정류소정보 API(좌표기반 근접 정류소 조회) 응답 구조를 눈으로 확인하는 탐색용 스크립트."""
import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / "backend" / ".env")
API_KEY = os.getenv("DATA_GO_KR_KEY")

URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"

params = {
    "serviceKey": API_KEY,
    "citycode": "21",       # TODO: 부산 도시코드 확인 필요 (다른 API들과 체계가 다를 가능성 높음)
    "gpsLati": "35.1504",   # 사상구 대략 중심 위도 (임시값, HIRA 데이터 기준)
    "gpsLong": "129.0083",  # 사상구 대략 중심 경도
    "numOfRows": 10,
    "pageNo": 1,
    "_type": "json",
}

response = requests.get(URL, params=params)
print("status_code:", response.status_code)
print(json.dumps(response.json(), ensure_ascii=False, indent=2))
