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

export default function AdminPage() {
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

      <p className="text-sm text-gray-500">
        데이터 즉시 최신화(FR-09) 기능이 이후 이 화면에 추가됩니다.
      </p>

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
        저장됩니다. 반경(r_c)·목표 개수(n_c)는 페르소나와 무관한 공통 값입니다. 입력란에서
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
              <div className="grid grid-cols-3 gap-3 text-sm items-end">
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
                <label className="space-y-1">
                  <span className="text-gray-500 block">반경 (r_c, m, 공통)</span>
                  <input
                    type="number"
                    step="1"
                    value={param.radius_m}
                    onChange={(e) => handleParamInput(cw.score_category, "radius_m", e.target.value)}
                    onBlur={(e) => handleParamBlur(cw.score_category, "radius_m", e.target.value)}
                    className="w-full border rounded px-2 py-1"
                  />
                </label>
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
