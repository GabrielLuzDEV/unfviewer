"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import LoginForm from "@/components/LoginForm";

type TwoFAMethod = "sms" | "app";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ipBanned, setIpBanned] = useState(false);
  const [needs2FA, setNeeds2FA] = useState(false);
  const [twoFAMethod, setTwoFAMethod] = useState<TwoFAMethod>("sms");
  const [code2FA, setCode2FA] = useState("");
  const [savedUsername, setSavedUsername] = useState("");

  useEffect(() => {
    setSavedUsername(localStorage.getItem("remembered_username") ?? "");
    // Check for existing valid session via cookie
    fetch(`${API}/auth/validate`, { credentials: "include" })
      .then((r) => { if (r.ok) return r.json(); throw new Error(); })
      .then((data) => {
        localStorage.setItem("username", data.username);
        router.replace("/dashboard");
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleLogin(username: string, password: string, rememberMe: boolean) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 403) setIpBanned(true);
        setError(data.detail ?? "Erro ao fazer login.");
        return;
      }
      if (rememberMe) localStorage.setItem("remembered_username", username);
      else localStorage.removeItem("remembered_username");
      if (data.awaiting_2fa) { setNeeds2FA(true); return; }
      if (typeof window !== "undefined" && window.PasswordCredential) {
        try { await navigator.credentials.store(new window.PasswordCredential({ id: username, password })); } catch {}
      }
      localStorage.setItem("username", data.username);
      router.push("/dashboard");
    } catch { setError("Não foi possível conectar ao servidor."); }
    finally { setLoading(false); }
  }

  async function handleCookieLogin(username: string, sessionid: string) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/login-cookie`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, sessionid }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Erro ao autenticar com cookie."); return; }
      localStorage.setItem("username", data.username);
      router.push("/dashboard");
    } catch { setError("Não foi possível conectar ao servidor."); }
    finally { setLoading(false); }
  }

  async function handleExportAnalyze(file: File) {
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/export/analyze`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Erro ao analisar exportação."); return; }
      // Store result in sessionStorage and navigate to dashboard in export mode
      sessionStorage.setItem("export_result", JSON.stringify(data));
      localStorage.setItem("username", "exportação");
      router.push("/dashboard?mode=export");
    } catch { setError("Não foi possível processar o arquivo."); }
    finally { setLoading(false); }
  }

  async function handle2FA() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/2fa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ code: code2FA }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Código inválido."); return; }
      localStorage.setItem("username", data.username);
      router.push("/dashboard");
    } catch { setError("Não foi possível conectar ao servidor."); }
    finally { setLoading(false); }
  }

  if (needs2FA) {
    const methodLabel =
      twoFAMethod === "sms"
        ? "Verifique seu SMS, WhatsApp ou e-mail e digite o código de 6 dígitos."
        : "Abra seu app autenticador (Google Authenticator, Authy etc.) e digite o código de 6 dígitos.";
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-8 space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">Verificação em duas etapas</h1>
            <p className="mt-1 text-sm text-gray-500">Escolha o método que o Instagram usou</p>
          </div>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm font-medium">
            {(["sms", "app"] as TwoFAMethod[]).map((m, i) => (
              <button
                key={m}
                onClick={() => { setTwoFAMethod(m); setCode2FA(""); setError(""); }}
                className={`flex-1 py-2 transition ${i > 0 ? "border-l border-gray-200" : ""} ${
                  twoFAMethod === m ? "bg-purple-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {m === "sms" ? "SMS / WhatsApp / E-mail" : "App autenticador"}
              </button>
            ))}
          </div>
          <p className="text-sm text-gray-500 text-center">{methodLabel}</p>
          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            placeholder="000000"
            value={code2FA}
            onChange={(e) => setCode2FA(e.target.value.replace(/\D/g, ""))}
            className="w-full border border-gray-300 rounded-lg px-4 py-2 text-center text-2xl tracking-widest focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
          <button
            onClick={handle2FA}
            disabled={loading || code2FA.length < 6}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white font-semibold py-2 rounded-lg transition"
          >
            {loading ? "Verificando..." : "Confirmar"}
          </button>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <LoginForm
        onLogin={handleLogin}
        onCookieLogin={handleCookieLogin}
        onExportAnalyze={handleExportAnalyze}
        loading={loading}
        error={error}
        savedUsername={savedUsername}
      />
    </main>
  );
}
