import { useState } from "react";
import SearchBar from "../components/SearchBar.jsx";
import { fetchGeocode } from "../api/geocode.js";
import { PERSONAS } from "../api/weights.js";

// 주소 검색 + 페르소나 선택만 담당. 점수·시설 결과는 SafetyMapPage에서 지도와 함께 한 번에 보여준다.
export default function ReportPage({ persona, onPersonaChange, onLocate } = {}) {
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

      <div className="flex gap-2 justify-center">
        {PERSONAS.map((p) => (
          <button
            key={p}
            onClick={() => onPersonaChange?.(p)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              persona === p ? "bg-blue-600 text-white" : "bg-gray-100"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-500 text-center">위치 찾는 중...</p>}
      {error && <p className="text-red-600 text-center">{error}</p>}

      <p className="text-sm text-gray-500 text-center">
        주소를 검색하거나 아래 지도를 클릭해 지점을 고른 뒤, 지도 오른쪽의 "정주여건 계산" 버튼을 누르면
        점수와 주변 시설이 지도 밑에 표시됩니다.
      </p>
    </div>
  );
}
