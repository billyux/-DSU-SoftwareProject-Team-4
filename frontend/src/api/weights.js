// 관리자 페이지: 점수 가중치 조회/수정 API 호출 함수 모음
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const PERSONAS = ["개인", "가족", "노인"];

// PERSONAS 값은 DB 가중치 테이블·API의 키라서 바꾸면 안 되고, 화면에는 이 이름으로 보여준다
export const PERSONA_LABELS = {
  개인: "개인/무자녀 가구",
  가족: "유자녀 가구",
  노인: "고령 가구",
};

async function handle(res, errorMessage) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || errorMessage);
  }
  return res.json();
}

// 반경(r_c)·목표 개수(n_c) — 페르소나 공통
export async function fetchCategoryParams() {
  const res = await fetch(`${API_BASE_URL}/api/admin/weights/categories`);
  return handle(res, "카테고리 파라미터를 불러오지 못했습니다.");
}

export async function updateCategoryParam(scoreCategory, body) {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/weights/categories/${encodeURIComponent(scoreCategory)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  return handle(res, "카테고리 파라미터를 저장하지 못했습니다.");
}

// 카테고리 가중치(W_c) — 페르소나별
export async function fetchPersonaCategoryWeights(persona) {
  const res = await fetch(`${API_BASE_URL}/api/admin/weights/personas/${encodeURIComponent(persona)}/categories`);
  return handle(res, "카테고리 가중치를 불러오지 못했습니다.");
}

export async function updatePersonaCategoryWeight(persona, scoreCategory, categoryWeight) {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/weights/personas/${encodeURIComponent(persona)}/categories/${encodeURIComponent(scoreCategory)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category_weight: categoryWeight }),
    }
  );
  return handle(res, "카테고리 가중치를 저장하지 못했습니다.");
}

// 시설 유형 가중치(wᵢ) — 페르소나별
export async function fetchPersonaFacilityTypeWeights(persona) {
  const res = await fetch(`${API_BASE_URL}/api/admin/weights/personas/${encodeURIComponent(persona)}/facility-types`);
  return handle(res, "시설 유형 가중치를 불러오지 못했습니다.");
}

export async function updatePersonaFacilityTypeWeight(persona, facilityType, weight) {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/weights/personas/${encodeURIComponent(persona)}/facility-types/${encodeURIComponent(facilityType)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weight }),
    }
  );
  return handle(res, "시설 유형 가중치를 저장하지 못했습니다.");
}
