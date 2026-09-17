import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchStats, fetchClients } from "../api/client";
import { Stats, Client } from "../api/types";
import StatusBadge from "../components/StatusBadge";
import { Users, CheckCircle, AlertCircle, Archive, Clock } from "lucide-react";

function fmtDate(s: string | null) {
  if (!s) return "Nunca";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function fmtSchedule(h: number, m: number) {
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
}

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStats().then(setStats);
    fetchClients().then(setClients);
  }, []);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Visão Geral</h1>
          <p className="page-subtitle">Status em tempo real de todos os clientes</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate("/clients")}>
          <Users size={15} /> Gerenciar Clientes
        </button>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Clientes Totais</span>
            <Users size={20} className="stat-icon" />
          </div>
          <div className="stat-value">{stats?.total_clients ?? "—"}</div>
          <div className="stat-sub">clientes cadastrados</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Ativos</span>
            <CheckCircle size={20} className="stat-icon" />
          </div>
          <div className="stat-value">{stats?.active_clients ?? "—"}</div>
          <div className="stat-sub">clientes com backup ativo</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Backups OK Hoje</span>
            <Archive size={20} className="stat-icon" />
          </div>
          <div className="stat-value value-ok">{stats?.backups_ok ?? "—"}</div>
          <div className="stat-sub">arquivos enviados hoje</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Erros Hoje</span>
            <AlertCircle size={20} className="stat-icon" />
          </div>
          <div className="stat-value" style={{ color: "var(--err)" }}>{stats?.backups_error ?? "—"}</div>
          <div className="stat-sub">falhas identificadas hoje</div>
        </div>
      </div>

      {/* Client cards */}
      <h2 className="section-title"><Users size={18} /> Clientes</h2>
      {clients.length === 0 ? (
        <div className="empty-state">
          <Users className="empty-icon" />
          <div>Nenhum cliente cadastrado ainda.</div>
          <button className="btn btn-primary mt-2" onClick={() => navigate("/clients")}>
            Cadastrar primeiro cliente
          </button>
        </div>
      ) : (
        <div className="clients-grid">
          {clients.map((c) => (
            <div key={c.id} className="client-card" onClick={() => navigate(`/clients/${c.id}`)}>
              <div className="client-card-header">
                <div className="flex gap-3 items-center">
                  <div className="client-avatar">
                    {c.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="client-name">{c.name}</div>
                    <div className="client-meta flex items-center gap-2">
                      <Clock size={12} />
                      {fmtSchedule(c.backup_hour, c.backup_minute)}
                    </div>
                  </div>
                </div>
                <StatusBadge status={c.last_backup_status} />
              </div>
              <div className="client-stats">
                <div className="client-stat-item">
                  <div className="client-stat-label">Equipamentos</div>
                  <div className="client-stat-value">{c.nvr_count}</div>
                </div>
                <div className="client-stat-item">
                  <div className="client-stat-label">Último backup</div>
                  <div className="client-stat-value" style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 500 }}>
                    {fmtDate(c.last_backup_at)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
