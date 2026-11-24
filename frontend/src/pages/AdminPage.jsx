import { useEffect, useState } from "react";
import {
  getRadiusLimit,
  setRadiusLimit,
  RADIUS_MIN,
  RADIUS_MAX,
  RADIUS_STEP,
} from "../lib/settings.js";
import {
  PERSONAS,
  PERSONA_LABELS,
  fetchCategoryParams,
  updateCategoryParam,
  fetchPersonaCategoryWeights,
  updatePersonaCategoryWeight,
  fetchPersonaFacilityTypeWeights,
  updatePersonaFacilityTypeWeight,
} from "../api/weights.js";
import { fetchFacilityRefreshStatus, startFacilityRefresh } from "../api/admin.js";

function describeRefreshResult(r) {
  switch (r.status) {
    case "waiting":
      return "대기 중";
    case "running":
      return "진행 중...";
    case "done":
      return `추가 ${r.added} · 삭제 ${r.removed} · 수정 ${r.updated} (현재 ${r.total}곳)`;
    case "error":
      return `실패 — ${r.error}`;
    default:
      return r.status;
  }
}

// FR-09: 상가·병원을 공공데이터 최신본과 비교해 DB에 바로 반영 (백엔드 services/facility_refresh.py)
function RefreshPanel({ adminPassword, children }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const running = status?.status === "running";

  useEffect(() => {
    fetchFacilityRefreshStatus().then(setStatus).catch(() => {});
  }, []);

  // 백그라운드 작업이라 끝날 때까지 2초마다 상태를 다시 가져온다
  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => {
      fetchFacilityRefreshStatus()
        .then(setStatus)
        .catch((e) => setError(e.message));
    }, 2000);
    return () => clearInterval(id);
  }, [running]);

  // 경과 시간은 서버가 기록한 시작 시각 기준으로 1초마다 다시 계산 (새로고침해도 이어짐)
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return undefined;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  const startedMs = status?.started_at ? new Date(status.started_at).getTime() : null;
  const elapsedSec = running && startedMs ? Math.max(0, Math.floor((now - startedMs) / 1000)) : 0;
  const estimatedSec = status?.estimated_seconds || 0;
  const expectedEnd = startedMs && estimatedSec ? new Date(startedMs + estimatedSec * 1000) : null;

  async function handleClick() {
    const ok = window.confirm(
      "상가·병원 정보를 공공데이터 최신본과 비교해 DB에 바로 반영합니다.\n없어진 시설은 삭제됩니다. 진행할까요?"
    );
    if (!ok) return;
    setError(null);
    try {
      setStatus(await startFacilityRefresh(adminPassword));
    } catch (e) {
      setError(e.message);
    }
  }

  // children(검색 범위 허용 최대값 박스)은 그대로 두고, 넓은 화면(xl)에서는 버튼을 박스 바깥 왼쪽 여백에
  // 같은 높이로 띄운다. 여백이 없는 좁은 화면에서는 박스 위에 한 줄로 보여준다. 실행 결과는 박스 아래에.
  return (
    <div className="space-y-3">
      <div className="relative">
        <button
          onClick={handleClick}
          disabled={running}
          title="상가·병원 정보를 공공데이터 최신본과 비교해 없어진 시설은 지우고 새 시설은 추가합니다"
          className="mb-3 w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300 xl:absolute xl:right-full xl:top-0 xl:mb-0 xl:mr-4 xl:h-full xl:w-36"
        >
          {running ? "최신화 중..." : "즉시 데이터 최신화"}
        </button>
        {children}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {running && (
        <div className="space-y-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          <p className="font-semibold">데이터 최신화 진행 중입니다. 잠시만 기다려주세요.</p>
          <div className="h-1.5 overflow-hidden rounded-full bg-blue-100">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-1000"
              style={{ width: `${estimatedSec ? Math.min(95, (elapsedSec / estimatedSec) * 100) : 0}%` }}
            />
          </div>
          <p className="tabular-nums">
            경과 시간 <span className="font-semibold">{elapsedSec}초</span>
            {expectedEnd && (
              <>
                {" "}· 예상 소요 약 {estimatedSec}초 (완료 예상{" "}
                {expectedEnd.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })})
              </>
            )}
          </p>
          {estimatedSec > 0 && elapsedSec > estimatedSec && (
            <p className="text-xs text-blue-700">예상보다 오래 걸리고 있습니다. 조금만 더 기다려주세요.</p>
          )}
        </div>
      )}
      {status && status.status !== "idle" && (
        <div className="space-y-1 rounded-lg border p-3 text-sm text-gray-700">
          <p className="font-medium">즉시 데이터 최신화 결과 (상가·병원)</p>
          {Object.entries(status.results).map(([label, r]) => (
            <p key={label} className={r.status === "error" ? "text-red-600" : ""}>
              <span className="font-medium">{label}</span>: {describeRefreshResult(r)}
            </p>
          ))}
          {status.error && <p className="text-red-600">{status.error}</p>}
          {status.finished_at && (
            <p className="text-xs text-gray-400">
              마지막 실행: {new Date(status.finished_at).toLocaleString("ko-KR")}
              {startedMs && ` (${Math.round((new Date(status.finished_at).getTime() - startedMs) / 1000)}초 걸림)`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminPage({ adminPassword }) {
  const [limit, setLimit] = useState(() => getRadiusLimit());
  const [saved, setSaved] = useState(false);

  function handleChange(e) {
    const value = Number(e.target.value);
    setLimit(value);
    setRadiusLimit(value);
    setSaved(true);
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">관리자 메뉴</h1>

      <RefreshPanel adminPassword={adminPassword}>
        <div className="p-4 rounded-lg border space-y-3">
          <h2 className="font-semibold">검색 범위 허용 최대값 설정 (FR-10)</h2>
          <p className="text-sm text-gray-500">
            메인 화면에서 사용자가 조절할 수 있는 검색 범위의 최대값입니다. 예를 들어 500m로 설정하면
            사용자는 지도에서 50m~500m 사이에서 반경을 직접 고를 수 있습니다. 설정한 값은 다음에
            메인 화면을 열 때부터 적용됩니다.
          </p>
          <input
            type="range"
            min={RADIUS_MIN}
            max={RADIUS_MAX}
            step={RADIUS_STEP}
            value={limit}
            onChange={handleChange}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>{RADIUS_MIN}m</span>
            <span className="text-base font-semibold text-gray-800">최대 {limit}m</span>
            <span>{RADIUS_MAX}m</span>
          </div>
          {saved && <p className="text-sm text-green-600">저장됨</p>}
        </div>
      </RefreshPanel>

      <WeightsEditor />
    </div>
  );
}

function WeightsEditor() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  const [categoryParams, setCategoryParams] = useState([]); // 공통(r_c, n_c)
  const [categoryWeights, setCategoryWeights] = useState([]); // 페르소나별(W_c)
  const [facilityTypes, setFacilityTypes] = useState([]); // 페르소나별(wᵢ)
  const [error, setError] = useState(null);
  const [savingKey, setSavingKey] = useState(null);

  useEffect(() => {
    setError(null);
    Promise.all([
      fetchCategoryParams(),
      fetchPersonaCategoryWeights(persona),
      fetchPersonaFacilityTypeWeights(persona),
    ])
      .then(([params, weights, types]) => {
        setCategoryParams(params);
        setCategoryWeights(weights);
        setFacilityTypes(types);
      })
      .catch((e) => setError(e.message));
  }, [persona]);

  // 입력 중인 값은 문자열이라(빈 칸 포함) 숫자로 바꿔서 더한다 — 그냥 더하면 문자열 이어붙이기가 되어 화면이 멈춤
  const weightSum = categoryWeights.reduce((sum, c) => sum + (Number(c.category_weight) || 0), 0);

  function handleParamInput(scoreCategory, field, value) {
    setCategoryParams((prev) =>
      prev.map((c) => (c.score_category === scoreCategory ? { ...c, [field]: value } : c))
    );
  }

  async function handleParamBlur(scoreCategory, field, rawValue) {
    const value = Number(rawValue);
    if (Number.isNaN(value)) return;
    setSavingKey(`param:${scoreCategory}:${field}`);
    try {
      await updateCategoryParam(scoreCategory, { [field]: value });
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingKey(null);
    }
  }

  function handleCategoryWeightInput(scoreCategory, value) {
    setCategoryWeights((prev) =>
      prev.map((c) => (c.score_category === scoreCategory ? { ...c, category_weight: value } : c))
    );
  }

  async function handleCategoryWeightBlur(scoreCategory, rawValue) {
    const value = Number(rawValue);
    if (Number.isNaN(value)) return;
    setSavingKey(`catw:${scoreCategory}`);
    try {
      await updatePersonaCategoryWeight(persona, scoreCategory, value);
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingKey(null);
    }
  }

  function handleFacilityTypeInput(facilityType, value) {
    setFacilityTypes((prev) =>
      prev.map((f) => (f.facility_type === facilityType ? { ...f, weight: value } : f))
    );
  }

  async function handleFacilityTypeBlur(facilityType, rawValue) {
    const value = Number(rawValue);
    if (Number.isNaN(value)) return;
    setSavingKey(`type:${facilityType}`);
    try {
      await updatePersonaFacilityTypeWeight(persona, facilityType, value);
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingKey(null);
    }
  }

  const paramsByCategory = categoryParams.reduce((acc, p) => {
    acc[p.score_category] = p;
    return acc;
  }, {});
  const typesByCategory = facilityTypes.reduce((acc, f) => {
    (acc[f.score_category] ||= []).push(f);
    return acc;
  }, {});

  return (
    <div className="p-4 rounded-lg border space-y-4">
      <h2 className="font-semibold">점수 가중치 설정</h2>
      <p className="text-sm text-gray-500">
        카테고리 가중치(W_c)와 시설 유형별 가중치(wᵢ)는 페르소나(개인/가족/노인)마다 따로
        저장됩니다. 목표 개수(n_c)는 페르소나와 무관한 공통 값입니다. 계산 반경은 사용자가 메인
        화면에서 고른 검색 범위를 쓰고, 종합병원만 별도의 최근접 검색 반경을 씁니다. 입력란에서
        벗어나면(blur) 자동 저장되고, 저장 즉시 재배포 없이 점수 계산에 반영됩니다.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        {PERSONAS.map((p) => (
          <button
            key={p}
            onClick={() => setPersona(p)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              persona === p ? "bg-blue-600 text-white" : "bg-gray-100"
            }`}
          >
            {PERSONA_LABELS[p]}
          </button>
        ))}
      </div>

      {Math.abs(weightSum - 1) > 0.01 ? (
        <div className="p-3 rounded-lg border-2 border-red-500 bg-red-50 text-red-700 text-sm space-y-1">
          <p className="font-bold">
            ⚠ [{PERSONA_LABELS[persona]}] 카테고리 가중치 합계가 {weightSum.toFixed(2)}입니다. 1.00이 되도록 맞춰주세요.
          </p>
          <p>합이 1이 아니면 점수가 그만큼 부풀거나 줄어듭니다 (예: 합 1.20 → 최대 120점).</p>
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          [{PERSONA_LABELS[persona]}] 카테고리 가중치 합계: {weightSum.toFixed(2)}
        </p>
      )}

      <div className="space-y-4">
        {categoryWeights.map((cw) => {
          const param = paramsByCategory[cw.score_category];
          if (!param) return null;
          return (
            <div key={cw.score_category} className="border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium">{cw.score_category}</span>
                {(savingKey === `catw:${cw.score_category}` ||
                  savingKey?.startsWith(`param:${cw.score_category}:`)) && (
                  <span className="text-xs text-gray-400">저장 중...</span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm items-end">
                <label className="space-y-1">
                  <span className="text-gray-500 block">가중치 (W_c, 페르소나별)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={cw.category_weight}
                    onChange={(e) => handleCategoryWeightInput(cw.score_category, e.target.value)}
                    onBlur={(e) => handleCategoryWeightBlur(cw.score_category, e.target.value)}
                    className="w-full border rounded px-2 py-1"
                  />
                </label>
                {/* 반경은 사용자가 메인 화면에서 고른 검색 범위를 쓴다. 종합병원만 최근접 검색 반경이 따로 있음 */}
                {cw.score_category === "의료_종합병원" ? (
                  <label className="space-y-1">
                    <span className="text-gray-500 block">최근접 검색 반경 (m, 공통)</span>
                    <input
                      type="number"
                      step="1"
                      value={param.radius_m}
                      onChange={(e) => handleParamInput(cw.score_category, "radius_m", e.target.value)}
                      onBlur={(e) => handleParamBlur(cw.score_category, "radius_m", e.target.value)}
                      className="w-full border rounded px-2 py-1"
                    />
                  </label>
                ) : (
                  <label className="space-y-1">
                    <span className="text-gray-500 block">목표 개수 (n_c, 공통)</span>
                    <input
                      type="number"
                      step="1"
                      value={param.target_count}
                      onChange={(e) => handleParamInput(cw.score_category, "target_count", e.target.value)}
                      onBlur={(e) => handleParamBlur(cw.score_category, "target_count", e.target.value)}
                      className="w-full border rounded px-2 py-1"
                    />
                  </label>
                )}
              </div>

              {typesByCategory[cw.score_category]?.length > 0 && (
                <div className="pt-2 space-y-1">
                  <span className="text-xs text-gray-500">[{PERSONA_LABELS[persona]}] 시설 유형별 가중치 (wᵢ)</span>
                  {typesByCategory[cw.score_category].map((f) => (
                    <div key={f.facility_type} className="flex items-center gap-2 text-sm">
                      <span className="flex-1">{f.facility_type}</span>
                      <input
                        type="number"
                        step="0.1"
                        value={f.weight}
                        onChange={(e) => handleFacilityTypeInput(f.facility_type, e.target.value)}
                        onBlur={(e) => handleFacilityTypeBlur(f.facility_type, e.target.value)}
                        className="w-24 border rounded px-2 py-1"
                      />
                      {savingKey === `type:${f.facility_type}` && (
                        <span className="text-xs text-gray-400">저장 중...</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
