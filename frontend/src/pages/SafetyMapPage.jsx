import { useEffect, useRef, useState } from "react";
import { fetchScoreByPoint } from "../api/score.js";
import { PERSONAS, PERSONA_LABELS } from "../api/weights.js";
import { getRadiusLimit, RADIUS_MIN, RADIUS_STEP } from "../lib/settings.js";
import { loadNaverSdk } from "../lib/naverMaps.js";

const SASANG_CENTER = { lat: 35.1524, lng: 128.9905 }; // 부산 사상구청 부근

// 지도 레이어 구분(facilities.category) 색상 — 선택 없이 전체 시설을 한 번에 보여주고
// 색으로만 구분한다 (학교·병원 등은 전부 "생활편의"로 같이 뜸)
const CATEGORY_COLORS = {
  안전: "#dc2626",
  생활편의: "#16a34a",
  음식점: "#f59e0b",
  교통: "#2563eb",
};
const DEFAULT_COLOR = "#6b7280";

const SCORE_CATEGORY_LABELS = {
  안전: "안전",
  의료_의원급: "의료(의원)",
  의료_종합병원: "의료(종합병원)",
  생필품: "생필품",
  버스: "버스",
  지하철: "지하철",
  교육: "교육(학교)",
  노인복지: "노인복지",
};

function makeDotIcon(naver, color) {
  return {
    content: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>`,
    anchor: new naver.maps.Point(7, 7),
  };
}

export default function SafetyMapPage({ focusPoint, persona, onPersonaChange } = {}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const naverRef = useRef(null);
  const overlaysRef = useRef([]);
  const infoWindowRef = useRef(null);
  const infoWindowMarkerRef = useRef(null);
  const searchIdRef = useRef(0);
  const lastClickRef = useRef(null);
  const pendingFocusRef = useRef(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [score, setScore] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);
  // 관리자 메뉴에서 설정한 허용 최대값은 지도가 열릴 때 한 번만 읽어온다(이후 변경은 다음 방문부터 적용)
  const [radiusLimit] = useState(() => getRadiusLimit());
  const [radiusM, setRadiusM] = useState(() => getRadiusLimit());
  const radiusRef = useRef(radiusM);
  const personaRef = useRef(persona);

  // 지도 클릭 리스너는 처음 한 번만 등록되기 때문에, 그 안에서 state를 직접 읽으면
  // 마운트 시점의 값에 고정돼버림(stale closure) — 그래서 ref로 최신 반경/페르소나를 추적함
  useEffect(() => {
    radiusRef.current = radiusM;
  }, [radiusM]);

  useEffect(() => {
    personaRef.current = persona;
  }, [persona]);

  // 주소 검색(ReportPage)에서 찾은 지점으로 지도를 이동시킨다. SDK/지도가 아직 준비 안 됐으면
  // pendingFocusRef에 저장해두고, 지도 초기화가 끝난 뒤 적용한다.
  function flyTo(lat, lng) {
    const naver = naverRef.current;
    const map = mapRef.current;
    if (!naver || !map) {
      pendingFocusRef.current = { lat, lng };
      return;
    }
    map.setCenter(new naver.maps.LatLng(lat, lng));
    map.setZoom(16);
    selectPoint(lat, lng);
  }

  function clearOverlays() {
    overlaysRef.current.forEach((overlay) => overlay.setMap(null));
    overlaysRef.current = [];
    // 시설 이름 말풍선은 마커와 별개로 지도에 붙어 있어서 따로 닫아야 한다
    infoWindowRef.current?.close();
  }

  // 지도 클릭·주소 검색은 지점에 마커만 찍는다. 시설 조회와 점수 계산은 "정주여건 계산" 버튼(searchAt)에서 한다
  function selectPoint(lat, lng) {
    const naver = naverRef.current;
    const map = mapRef.current;
    if (!naver || !map) return;

    searchIdRef.current += 1; // 진행 중이던 계산의 응답이 늦게 와도 무시되도록
    clearOverlays();
    overlaysRef.current = [new naver.maps.Marker({ position: new naver.maps.LatLng(lat, lng), map })];

    lastClickRef.current = { lat, lng };
    setSelectedPoint({ lat, lng });
    setResult(null);
    setScore(null);
    setError(null);
  }

  async function searchAt(lat, lng) {
    const naver = naverRef.current;
    const map = mapRef.current;
    if (!naver || !map) return;

    // 빠르게 여러 번 클릭하면 이전 요청의 응답이 늦게 도착할 수 있어서, 최신 요청 응답만 반영한다
    const searchId = ++searchIdRef.current;

    clearOverlays();

    const position = new naver.maps.LatLng(lat, lng);
    const marker = new naver.maps.Marker({ position, map });
    const circle = new naver.maps.Circle({
      map,
      center: position,
      radius: radiusRef.current,
      strokeWeight: 2,
      strokeColor: "#2563eb",
      strokeOpacity: 0.8,
      fillColor: "#3b82f6",
      fillOpacity: 0.2,
    });
    overlaysRef.current = [marker, circle];

    setResult({ lat, lng, loading: true });
    setScore(null);
    setError(null);
    try {
      const scoreResult = await fetchScoreByPoint(lat, lng, personaRef.current, radiusRef.current);
      if (searchId !== searchIdRef.current) return;

      // 지도·목록에는 점수 계산에 실제로 쓰인 시설만 보여준다 (이 페르소나에서 가중치가 있는 카테고리, 반경 안).
      // 종합병원은 반경 밖(최대 5km) 최근접 거리로 계산되므로 지도에 그리지 않고 결과에 따로 표시
      const usedFacilities = scoreResult.categories
        .filter((c) => c.category_weight > 0 && c.score_category !== "의료_종합병원")
        .flatMap((c) => c.nearby)
        .sort((a, b) => a.distance_m - b.distance_m);
      const nearestHospital =
        scoreResult.categories.find((c) => c.score_category === "의료_종합병원")?.nearby[0] || null;

      const facilityMarkers = usedFacilities.map((f) => {
        const color = CATEGORY_COLORS[f.category] || DEFAULT_COLOR;
        const fMarker = new naver.maps.Marker({
          position: new naver.maps.LatLng(f.latitude, f.longitude),
          map,
          icon: makeDotIcon(naver, color),
          title: f.name || f.facility_type,
          zIndex: 50,
        });

        naver.maps.Event.addListener(fMarker, "click", () => {
          const infoWindow = infoWindowRef.current;
          // 이미 이 마커의 말풍선이 열려 있으면 다시 클릭했을 때 닫는다
          if (infoWindow.getMap() && infoWindowMarkerRef.current === fMarker) {
            infoWindow.close();
            return;
          }
          infoWindowMarkerRef.current = fMarker;
          infoWindow.setContent(
            `<div style="padding:6px 10px;font-size:12px;">${f.name || f.facility_type}<br/>${f.facility_type} · ${f.distance_m}m</div>`
          );
          infoWindow.open(map, fMarker);
        });

        return fMarker;
      });

      overlaysRef.current = [...overlaysRef.current, ...facilityMarkers];

      setResult({ lat, lng, count: usedFacilities.length, facilities: usedFacilities, nearestHospital });
      setScore(scoreResult);
    } catch (e) {
      if (searchId !== searchIdRef.current) return;
      setError(e.message);
      setResult(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    loadNaverSdk()
      .then((naver) => {
        if (cancelled || !mapContainerRef.current) return;
        naverRef.current = naver;

        const map = new naver.maps.Map(mapContainerRef.current, {
          center: new naver.maps.LatLng(SASANG_CENTER.lat, SASANG_CENTER.lng),
          zoom: 15,
        });
        mapRef.current = map;
        infoWindowRef.current = new naver.maps.InfoWindow({ content: "" });

        naver.maps.Event.addListener(map, "click", (pointerEvent) => {
          const lat = pointerEvent.coord.lat();
          const lng = pointerEvent.coord.lng();
          selectPoint(lat, lng);
        });

        if (pendingFocusRef.current) {
          const { lat, lng } = pendingFocusRef.current;
          pendingFocusRef.current = null;
          flyTo(lat, lng);
        }
      })
      .catch((e) => setError(e.message));

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 검색 범위나 페르소나를 바꾸면 이전 계산 결과는 맞지 않으므로 지우고, 마커만 남겨 다시 계산하게 한다
  useEffect(() => {
    if (lastClickRef.current) {
      selectPoint(lastClickRef.current.lat, lastClickRef.current.lng);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radiusM, persona]);

  // 주소 검색(ReportPage)에서 좌표를 찾으면 지도를 그 지점으로 이동
  useEffect(() => {
    if (focusPoint) flyTo(focusPoint.lat, focusPoint.lng);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPoint]);

  return (
    <div className="space-y-4">
      {error && <p className="text-red-600">{error}</p>}

      <div className="flex flex-col md:flex-row gap-4">
        <div ref={mapContainerRef} className="flex-1 h-[420px] rounded-lg border" />

        <div className="w-full md:w-56 shrink-0 space-y-3 self-start">
          <button
            onClick={() => selectedPoint && searchAt(selectedPoint.lat, selectedPoint.lng)}
            disabled={!selectedPoint || result?.loading}
            className="w-full px-4 py-3 rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {result?.loading ? "계산 중..." : "정주여건 계산"}
          </button>
          {!selectedPoint && (
            <p className="text-xs text-gray-500 text-center">지도를 클릭하거나 주소를 검색해 지점을 먼저 고르세요.</p>
          )}

          <div className="p-4 rounded-lg border space-y-3">
            <h2 className="font-semibold text-sm">검색 범위</h2>
            <input
              type="range"
              min={RADIUS_MIN}
              max={radiusLimit}
              step={RADIUS_STEP}
              value={radiusM}
              onChange={(e) => setRadiusM(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-400">
              <span>{RADIUS_MIN}m</span>
              <span className="text-base font-semibold text-gray-800">{radiusM}m</span>
              <span>{radiusLimit}m</span>
            </div>

            <div className="flex flex-col gap-1.5">
              {PERSONAS.map((p) => (
                <button
                  key={p}
                  onClick={() => onPersonaChange?.(p)}
                  className={`w-full px-3 py-1.5 rounded-lg text-sm ${
                    persona === p ? "bg-blue-600 text-white" : "bg-gray-100"
                  }`}
                >
                  {PERSONA_LABELS[p]}
                </button>
              ))}
            </div>

            <div className="pt-3 border-t space-y-1 text-xs text-gray-600">
              {Object.entries(CATEGORY_COLORS).map(([category, color]) => (
                <div key={category} className="flex items-center gap-2">
                  <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                  {category === "생활편의" ? "생활편의(학교·병원 포함)" : category}
                </div>
              ))}
              <p className="pt-1 text-gray-400">점을 클릭하면 시설 이름이 뜹니다.</p>
            </div>
          </div>
        </div>
      </div>

      {(score || result) && (
        <div className="p-4 rounded-lg border bg-white space-y-4">
          {score && (
            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-gray-500">[{PERSONA_LABELS[persona]}] 정주여건 점수</span>
                <span className="text-3xl font-bold">{score.total_score}점</span>
              </div>
              <div className="space-y-2">
                {score.categories
                  // 종합병원은 의원급과 합산되고, 가중치 0인 카테고리는 이 페르소나 계산에 안 들어가므로 숨김
                  .filter((c) => c.score_category !== "의료_종합병원" && c.category_weight > 0)
                  .map((c) => (
                    <div key={c.score_category} className="flex items-center gap-2">
                      <span className="w-24 text-sm text-gray-600">
                        {SCORE_CATEGORY_LABELS[c.score_category] || c.score_category}
                      </span>
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500" style={{ width: `${Math.round(c.score * 100)}%` }} />
                      </div>
                      <span className="w-10 text-right text-sm text-gray-500">{Math.round(c.score * 100)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {result && (
            <div className={`space-y-2 ${score ? "pt-4 border-t" : ""}`}>
              <p className="text-sm text-gray-500">
                클릭 좌표: {result.lat.toFixed(5)}, {result.lng.toFixed(5)}
              </p>
              <p className="text-lg font-semibold">
                반경 {radiusM}m 내 점수에 반영된 시설: {result.loading ? "조회 중..." : `${result.count}개`}
              </p>
              {!result.loading && (
                <p className="text-sm text-gray-600">
                  가장 가까운 종합병원:{" "}
                  {result.nearestHospital
                    ? `${result.nearestHospital.name} (${(result.nearestHospital.distance_m / 1000).toFixed(1)}km)`
                    : "5km 안에 없음"}
                </p>
              )}

              {result.facilities && result.facilities.length > 0 && (
                <ul className="text-sm text-gray-700 divide-y max-h-64 overflow-y-auto">
                  {result.facilities.map((f, i) => (
                    <li key={i} className="py-1 flex justify-between gap-2">
                      <span className="truncate">
                        <span
                          className="inline-block w-2 h-2 rounded-full mr-2"
                          style={{ backgroundColor: CATEGORY_COLORS[f.category] || DEFAULT_COLOR }}
                        />
                        {f.name || f.facility_type}
                        <span className="text-gray-400"> · {f.facility_type}</span>
                      </span>
                      <span className="text-gray-400 shrink-0">{f.distance_m}m</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
