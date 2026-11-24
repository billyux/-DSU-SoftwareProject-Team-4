// 관리자 '즉시 데이터 최신화'(FR-09) API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parse(res, fallback) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || fallback);
  }
  return res.json();
}

export async function startFacilityRefresh(adminPassword) {
  const res = await fetch(`${API_BASE_URL}/api/admin/refresh`, {
    method: "POST",
    headers: { "X-Admin-Password": adminPassword },
  });
  return parse(res, "데이터 최신화를 시작하지 못했습니다.");
}

export async function fetchFacilityRefreshStatus() {
  const res = await fetch(`${API_BASE_URL}/api/admin/refresh/status`);
  return parse(res, "최신화 상태를 불러오지 못했습니다.");
}
