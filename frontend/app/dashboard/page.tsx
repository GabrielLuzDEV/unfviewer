"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import NonFollowerList from "@/components/NonFollowerList";

interface NonFollower {
  username: string;
  followers: number;
  profile_pic_url: string | null;
  is_verified: boolean;
}

type FetchState = "idle" | "fetching" | "done" | "error";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  return (
    <Suspense>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isExportMode = searchParams.get("mode") === "export";

  const [fetchState, setFetchState] = useState<FetchState>("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [nonFollowers, setNonFollowers] = useState<NonFollower[]>([]);
  const [username, setUsername] = useState("");
  const [unfollowError, setUnfollowError] = useState("");
  const [cooldownSec, setCooldownSec] = useState(0);  // seconds remaining in cooldown
  const esRef = useRef<EventSource | null>(null);
  const cooldownRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const user = localStorage.getItem("username") ?? "";
    setUsername(user);

    if (isExportMode) {
      // Load pre-analyzed result from sessionStorage
      const raw = sessionStorage.getItem("export_result");
      if (!raw) { router.replace("/"); return; }
      try {
        const data = JSON.parse(raw);
        setNonFollowers(data.non_followers ?? []);
        setFetchState("done");
      } catch {
        router.replace("/");
      }
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      if (cancelled) return;
      fetch(`${API}/auth/validate`, { credentials: "include" })
        .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
        .then((data) => {
          if (cancelled) return;
          localStorage.setItem("username", data.username);
          setUsername(data.username);
          startFetch();
        })
        .catch(() => {
          if (!cancelled) {
            localStorage.removeItem("username");
            localStorage.removeItem("remembered_username");
            router.replace("/");
          }
        });
    }, 150);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  // Cooldown countdown ticker
  useEffect(() => {
    if (cooldownSec <= 0) {
      if (cooldownRef.current) { clearInterval(cooldownRef.current); cooldownRef.current = null; }
      return;
    }
    cooldownRef.current = setInterval(() => {
      setCooldownSec((s) => {
        if (s <= 1) { clearInterval(cooldownRef.current!); cooldownRef.current = null; return 0; }
        return s - 1;
      });
    }, 1000);
    return () => { if (cooldownRef.current) clearInterval(cooldownRef.current); };
  }, [cooldownSec > 0]);

  function startFetch() {
    esRef.current?.close();
    setFetchState("fetching");
    setStatusMsg("Conectando...");
    setWarnings([]);
    setUnfollowError("");

    const es = new EventSource(`${API}/followers/non-followers/stream`, { withCredentials: true });
    esRef.current = es;

    es.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "progress") {
        setStatusMsg(msg.message);
      } else if (msg.type === "warning") {
        setWarnings((prev) => [...prev, msg.message]);
      } else if (msg.type === "done") {
        setNonFollowers(msg.non_followers);
        setFetchState("done");
        es.close(); esRef.current = null;
      } else if (msg.type === "busy") {
        setStatusMsg("Conectando à busca em andamento...");
        es.close(); esRef.current = null;
        setTimeout(startFetch, (msg.retry_after ?? 3) * 1000);
      } else if (msg.type === "error") {
        setStatusMsg(msg.message);
        setFetchState("error");
        es.close(); esRef.current = null;
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      setStatusMsg("Erro de conexão com o servidor.");
      setFetchState("error");
      es.close(); esRef.current = null;
    };
  }

  async function handleUnfollow(targetUsername: string): Promise<boolean> {
    setUnfollowError("");
    const res = await fetch(`${API}/unfollow/${encodeURIComponent(targetUsername)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username: targetUsername }),
    });

    if (res.status === 429) {
      const data = await res.json();
      const retryAfter = parseInt(res.headers.get("Retry-After") ?? "300", 10);
      setCooldownSec(retryAfter);
      setUnfollowError(data.detail ?? "Pausa de segurança ativa.");
      return false;
    }
    if (!res.ok) {
      const data = await res.json();
      setUnfollowError(data.detail ?? "Erro ao deixar de seguir.");
      return false;
    }
    return true;
  }

  async function handleLogout() {
    esRef.current?.close();
    if (!isExportMode) {
      await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    }
    localStorage.removeItem("username");
    localStorage.removeItem("remembered_username");
    sessionStorage.removeItem("export_result");
    router.replace("/");
  }

  function formatCountdown(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  return (
    <main className="max-w-2xl mx-auto p-4 space-y-6">
      <header className="flex items-center justify-between pt-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Não seguem de volta</h1>
          {username && <p className="text-sm text-gray-500">@{username}</p>}
          {isExportMode && (
            <span className="inline-block mt-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              modo exportação
            </span>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-400 hover:text-gray-600 transition"
        >
          Sair
        </button>
      </header>

      {cooldownSec > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center gap-3">
          <div className="text-2xl font-mono font-bold text-amber-700 min-w-[4rem] text-center">
            {formatCountdown(cooldownSec)}
          </div>
          <div>
            <p className="text-amber-800 font-medium text-sm">Pausa de segurança</p>
            <p className="text-amber-600 text-xs">
              Para proteger sua conta, aguarde antes de continuar desfazendo seguimentos.
            </p>
          </div>
        </div>
      )}

      {unfollowError && cooldownSec === 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {unfollowError}
        </div>
      )}

      {fetchState === "fetching" && (
        <div className="bg-white rounded-2xl shadow p-6 text-center space-y-3">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-purple-600 mx-auto" />
          <p className="text-gray-600">{statusMsg || "Buscando dados..."}</p>
          <p className="text-xs text-gray-400">Isso pode levar alguns minutos.</p>
        </div>
      )}

      {fetchState === "error" && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center space-y-3">
          <p className="text-red-700 font-medium">Algo deu errado</p>
          <p className="text-red-500 text-sm">{statusMsg}</p>
          <div className="flex justify-center gap-3 mt-2">
            <button
              onClick={startFetch}
              className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition"
            >
              Tentar novamente
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-white border border-gray-300 text-gray-600 text-sm rounded-lg hover:bg-gray-50 transition"
            >
              Fazer login novamente
            </button>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-1">
          <p className="text-amber-800 font-medium text-sm">Busca parcial — Instagram aplicou limite de taxa</p>
          {warnings.map((w, i) => (
            <p key={i} className="text-amber-700 text-xs">{w}</p>
          ))}
        </div>
      )}

      {fetchState === "done" && (
        <NonFollowerList
          nonFollowers={nonFollowers}
          onUnfollow={isExportMode ? undefined : handleUnfollow}
        />
      )}
    </main>
  );
}
