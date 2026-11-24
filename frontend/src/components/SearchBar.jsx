import { useState } from "react";

export default function SearchBar({ onSearch }) {
  const [address, setAddress] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (address.trim()) onSearch(address.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="relative flex-1">
        <svg
          className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="예: 부산광역시 사상구청"
          className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 text-[15px] shadow-sm transition placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/10"
        />
      </div>
      <button
        type="submit"
        className="rounded-xl bg-blue-600 px-5 font-semibold text-white shadow-sm transition hover:bg-blue-700"
      >
        검색
      </button>
    </form>
  );
}
