// 백엔드 점수 계산 API 호출 (주소 -> 페르소나별 정주여건 점수)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchScore(address, persona) {
  const params = new URLSearchParams({ address, persona });
  const res = await fetch(`${API_BASE_URL}/api/score?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "점수를 계산하지 못했습니다.");
  }
  return res.json();
}

// radiusM: 사용자 검색 반경 — 종합병원을 뺀 모든 카테고리가 이 반경 안의 시설로 계산됨
export async function fetchScoreByPoint(lat, lng, persona, radiusM) {
  const params = new URLSearchParams({ lat, lng, persona, radius_m: radiusM });
  const res = await fetch(`${API_BASE_URL}/api/score/point?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "점수를 계산하지 못했습니다.");
  }
  return res.json();
}
