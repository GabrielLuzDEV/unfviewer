"use client";

import { useEffect, useRef, useState } from "react";

type LoginMode = "password" | "cookie" | "export";

interface Props {
  onLogin: (username: string, password: string, rememberMe: boolean) => void;
  onCookieLogin: (username: string, sessionid: string) => void;
  onExportAnalyze: (file: File) => void;
  loading: boolean;
  error: string;
  savedUsername?: string;
  ipBanned?: boolean;
}

export default function LoginForm({
  onLogin,
  onCookieLogin,
  onExportAnalyze,
  loading,
  error,
  savedUsername = "",
  ipBanned = false,
}: Props) {
  const [mode, setMode] = useState<LoginMode>(ipBanned ? "cookie" : "password");

  useEffect(() => {
    if (ipBanned) setMode("cookie");
  }, [ipBanned]);
  const [username, setUsername] = useState(savedUsername);
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(!!savedUsername);
  const [sessionid, setSessionid] = useState("");
  const [exportFile, setExportFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (savedUsername && !username) {
      setUsername(savedUsername);
      setRememberMe(true);
    }
  }, [savedUsername]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "password" && username && password) {
      onLogin(username.replace("@", ""), password, rememberMe);
    } else if (mode === "cookie" && sessionid) {
      onCookieLogin(username.replace("@", ""), sessionid.trim());
    } else if (mode === "export" && exportFile) {
      onExportAnalyze(exportFile);
    }
  }

  const tabs: { id: LoginMode; label: string }[] = [
    { id: "password", label: "Senha" },
    { id: "cookie", label: "Cookie" },
    { id: "export", label: "Exportação" },
  ];

  return (
    <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-8 space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">unfviewer</h1>
        <p className="mt-2 text-sm text-gray-500">
          Descubra quem não segue você de volta
        </p>
      </div>

      {ipBanned && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 space-y-1">
          <p className="font-semibold">Login com senha bloqueado pelo Instagram</p>
          <p>O IP deste servidor está na lista negra do Instagram. Use o <strong>Cookie de sessão</strong> abaixo:</p>
          <ol className="list-decimal list-inside space-y-0.5 text-amber-700">
            <li>Abra <strong>instagram.com</strong> no navegador e faça login</li>
            <li>Pressione <strong>F12</strong> → aba <strong>Application</strong></li>
            <li>Cookies → <strong>https://www.instagram.com</strong></li>
            <li>Copie o valor de <strong>sessionid</strong> e cole abaixo</li>
          </ol>
        </div>
      )}

      {/* Mode tabs */}
      <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm font-medium">
        {tabs.map((tab, i) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setMode(tab.id)}
            className={`flex-1 py-2 transition ${
              i > 0 ? "border-l border-gray-200" : ""
            } ${
              mode === tab.id
                ? "bg-purple-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "password" && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuário do Instagram
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="@seuperfil"
                required
                autoComplete="username"
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Senha
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="rememberMe"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500 cursor-pointer"
              />
              <label htmlFor="rememberMe" className="text-sm text-gray-600 cursor-pointer select-none">
                Lembrar meu usuário
              </label>
            </div>
          </>
        )}

        {mode === "cookie" && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuário do Instagram
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="@seuperfil"
                required
                autoComplete="username"
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Cookie <code className="bg-gray-100 px-1 rounded text-xs">sessionid</code>
              </label>
              <textarea
                value={sessionid}
                onChange={(e) => setSessionid(e.target.value)}
                placeholder="Cole aqui o valor do cookie sessionid..."
                required
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              />
              <p className="mt-1 text-xs text-gray-400">
                instagram.com → F12 → Application → Cookies → copie o valor de <code>sessionid</code>
              </p>
            </div>
          </>
        )}

        {mode === "export" && (
          <div className="space-y-3">
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-700 space-y-1">
              <p className="font-medium">Sem login necessário</p>
              <p>Baixe seus dados em: Instagram → Configurações → Sua atividade → Baixar suas informações → JSON</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Arquivo ZIP do Instagram
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".zip"
                required
                onChange={(e) => setExportFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100 cursor-pointer"
              />
              {exportFile && (
                <p className="mt-1 text-xs text-gray-500">{exportFile.name} ({(exportFile.size / 1024 / 1024).toFixed(1)} MB)</p>
              )}
            </div>
          </div>
        )}

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading || (mode === "export" && !exportFile)}
          className="w-full bg-gradient-to-r from-purple-600 to-pink-500 hover:opacity-90 disabled:opacity-50 text-white font-semibold py-2 rounded-lg transition"
        >
          {loading
            ? mode === "export" ? "Analisando..." : "Entrando..."
            : mode === "export" ? "Analisar exportação" : "Entrar com Instagram"}
        </button>
      </form>

      <p className="text-xs text-gray-400 text-center leading-relaxed">
        Sua senha/cookie vai direto ao Instagram e é descartada imediatamente.
        Nunca armazenamos credenciais.
      </p>
    </div>
  );
}
