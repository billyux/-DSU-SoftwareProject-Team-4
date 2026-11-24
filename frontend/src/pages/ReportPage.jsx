import { useState } from "react";
import SearchBar from "../components/SearchBar.jsx";
import { fetchGeocode } from "../api/geocode.js";

// 주소 검색만 담당. 페르소나 선택·점수·시설 결과는 SafetyMapPage에서 지도와 함께 보여준다.
export default function ReportPage({ onLocate } = {}) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(address) {
    setError(null);
    setLoading(true);
    try {
      const point = await fetchGeocode(address);
      if (onLocate) onLocate(point);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      <SearchBar onSearch={handleSearch} />

      {loading && <p className="text-sm text-gray-500 text-center">위치 찾는 중...</p>}
      {error && <p className="text-red-600 text-center">{error}</p>}

      <p className="text-sm text-gray-500 text-center">
        주소를 검색하거나 아래 지도를 클릭해 지점을 고른 뒤, 지도 오른쪽의 "정주여건 계산" 버튼을 누르면
        점수와 주변 시설이 지도 밑에 표시됩니다.
      </p>
    </div>
  );
}
