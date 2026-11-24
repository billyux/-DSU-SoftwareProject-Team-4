import { useState } from "react";
import ReportPage from "./pages/ReportPage.jsx";
import SafetyMapPage from "./pages/SafetyMapPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import { PERSONAS } from "./api/weights.js";

// FR-08: 관리자 메뉴 진입 - 클라이언트에서만 확인하는 암호라, 개발자도구로 코드를 보면
// 누구나 알 수 있다. 실제 운영에선 서버 쪽 인증으로 바꿔야 함.
const ADMIN_PASSWORD = "12345";

export default function App() {
  const [view, setView] = useState("main"); // "main" | "admin"
  const [showPasswordPrompt, setShowPasswordPrompt] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState(null);
  const [focusPoint, setFocusPoint] = useState(null);
  const [persona, setPersona] = useState(PERSONAS[0]);

  function openPasswordPrompt() {
    setPassword("");
    setPasswordError(null);
    setShowPasswordPrompt(true);
  }

  function handleAdminSubmit(e) {
    e.preventDefault();
    if (password === ADMIN_PASSWORD) {
      setView("admin");
      setShowPasswordPrompt(false);
    } else {
      setPasswordError("암호가 올바르지 않습니다.");
    }
  }

  return (
    <div>
      <nav className="flex justify-between items-center p-4 border-b">
        <span className="text-xl font-bold">동네 진단</span>
        {view === "main" ? (
          <button
            onClick={openPasswordPrompt}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-100"
          >
            관리자
          </button>
        ) : (
          <button
            onClick={() => setView("main")}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-100"
          >
            메인으로
          </button>
        )}
      </nav>

      {showPasswordPrompt && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <form
            onSubmit={handleAdminSubmit}
            className="bg-white rounded-lg p-6 w-80 space-y-3 shadow-xl"
          >
            <h2 className="font-semibold">관리자 암호 입력</h2>
            <input
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2"
              placeholder="암호를 입력하세요"
            />
            {passwordError && <p className="text-red-600 text-sm">{passwordError}</p>}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowPasswordPrompt(false)}
                className="px-3 py-1.5 rounded-lg text-sm bg-gray-100"
              >
                취소
              </button>
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg text-sm bg-blue-600 text-white"
              >
                확인
              </button>
            </div>
          </form>
        </div>
      )}

      {view === "admin" ? (
        <AdminPage />
      ) : (
        <div className="max-w-5xl mx-auto p-4 space-y-4">
          <ReportPage persona={persona} onPersonaChange={setPersona} onLocate={setFocusPoint} />
          <SafetyMapPage persona={persona} focusPoint={focusPoint} />
        </div>
      )}
    </div>
  );
}
