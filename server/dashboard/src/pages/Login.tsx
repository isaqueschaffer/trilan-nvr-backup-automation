import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Lock, Server } from "lucide-react";

export default function Login() {
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      await login(pw);
      navigate("/");
    } catch {
      setError("Senha incorreta. Tente novamente.");
    } finally { setLoading(false); }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-icon">
            <Server size={28} color="white" />
          </div>
          <div className="login-logo-title">TRILAN NVR</div>
          <div className="login-logo-sub">Painel de Backup Centralizado</div>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Senha de administrador</label>
            <div style={{ position: "relative" }}>
              <input
                className="form-input"
                type="password"
                placeholder="••••••••"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                style={{ paddingLeft: 40 }}
                autoFocus
              />
              <Lock size={15} style={{
                position: "absolute", left: 12, top: "50%",
                transform: "translateY(-50%)", color: "var(--text-muted)"
              }} />
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary w-full"
            style={{ justifyContent: "center", marginTop: 8 }}
            disabled={loading}
          >
            {loading ? <span className="spinner spinner-sm" /> : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
