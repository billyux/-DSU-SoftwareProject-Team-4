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
  const [adminPassword, setAdminPassword] = useState("");
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
      // 데이터 최신화처럼 DB를 바꾸는 요청은 서버에서 이 암호를 다시 확인한다
      setAdminPassword(password);
      setView("admin");
      setShowPasswordPrompt(false);
    } else {
      setPasswordError("암호가 올바르지 않습니다.");
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <nav className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
              <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="currentColor" aria-hidden="true">
                <path d="M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z" />
              </svg>
            </span>
            <span className="text-lg font-bold tracking-tight">동네 진단</span>
            <span className="hidden text-sm text-slate-400 sm:inline">부산 사상구 정주여건 진단</span>
          </div>
          {view === "main" ? (
            <button
              onClick={openPasswordPrompt}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              관리자
            </button>
          ) : (
            <button
              onClick={() => setView("main")}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              메인으로
            </button>
          )}
        </div>
      </nav>

      {showPasswordPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
          <form
            onSubmit={handleAdminSubmit}
            className="w-80 space-y-4 rounded-2xl bg-white p-6 shadow-xl"
          >
            <h2 className="font-semibold">관리자 암호 입력</h2>
            <input
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/10"
              placeholder="암호를 입력하세요"
            />
            {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowPasswordPrompt(false)}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
              >
                취소
              </button>
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                확인
              </button>
            </div>
          </form>
        </div>
      )}

      {view === "admin" ? (
        <AdminPage adminPassword={adminPassword} />
      ) : (
        <main className="mx-auto max-w-5xl space-y-5 px-4 py-6">
          <ReportPage onLocate={setFocusPoint} />
          <SafetyMapPage persona={persona} onPersonaChange={setPersona} focusPoint={focusPoint} />
        </main>
      )}
    </div>
  );
}
