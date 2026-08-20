import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  fetchClient, fetchNVRs, createNVR, deleteNVR, updateClient,
  rotateKey, fetchBackups, restartAgent
} from "../api/client";
import { Client, NVR, Backup } from "../api/types";
import StatusBadge from "../components/StatusBadge";
import Modal from "../components/Modal";
import { useToast } from "../components/Toast";
import { ArrowLeft, Plus, Trash2, RefreshCw, Copy, Edit2, Server, Archive, RotateCcw } from "lucide-react";

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR");
}

function MiniCalendar({ mapStr, referenceDate }: { mapStr: string; referenceDate: string | null }) {
  if (!mapStr) return <span>—</span>;
  
  const refDate = referenceDate ? new Date(referenceDate) : new Date();
  
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "4px", width: "fit-content" }}>
      {mapStr.split("").map((char, i) => {
        const isOk = char === "█";
        const daysAgo = (mapStr.length - 1) - i;
        
        const d = new Date(refDate);
        d.setDate(d.getDate() - daysAgo);
        const dateStr = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
        
        return (
          <div
            key={i}
            title={`${dateStr}: ${isOk ? "Gravou" : "Falhou"}`}
            className="flex-col items-center justify-center"
            style={{
              width: 26,
              height: 18,
              flexShrink: 0,
              borderRadius: 2,
              backgroundColor: isOk ? "var(--ok)" : "var(--err)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: "white",
              display: "flex",
              cursor: "help",
              transition: "transform 0.1s"
            }}
            onMouseEnter={e => e.currentTarget.style.transform = "scale(1.15)"}
            onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
          >
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "-0.3px" }}>{dateStr}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function ClientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [client, setClient] = useState<Client | null>(null);
  const [nvrs, setNVRs] = useState<NVR[]>([]);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);

  const [showNVRModal, setShowNVRModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showRecordingModal, setShowRecordingModal] = useState<{show: boolean, nvrName: string, cameras: any[]}>({show: false, nvrName: "", cameras: []});
  const [rotatedKey, setRotatedKey] = useState<string | null>(null);
  const [nvrForm, setNvrForm] = useState({ name: "", ip: "", username: "", password: "" });
  const [editForm, setEditForm] = useState<Partial<Client> & { zip_password?: string }>({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!id) return;
    const [c, n, b] = await Promise.all([
      fetchClient(id),
      fetchNVRs(id),
      fetchBackups({ client_id: id, size: 10 }),
    ]);
    setClient(c); setNVRs(n); setBackups(b.items);
    setLoading(false);
  };
  useEffect(() => { load(); }, [id]);

  const handleAddNVR = async () => {
    if (!nvrForm.name || !nvrForm.ip || !nvrForm.username || !nvrForm.password) {
      toast("Preencha todos os campos.", "error"); return;
    }
    setSaving(true);
    try {
      await createNVR(id!, nvrForm);
      toast("NVR adicionado!", "success");
      setShowNVRModal(false);
      setNvrForm({ name: "", ip: "", username: "", password: "" });
      load();
    } catch { toast("Erro ao adicionar NVR.", "error"); }
    finally { setSaving(false); }
  };

  const handleDeleteNVR = async (nvrId: string, name: string) => {
    if (!confirm(`Remover NVR "${name}"?`)) return;
    await deleteNVR(id!, nvrId);
    toast("NVR removido.", "success");
    load();
  };

  const handleEditSave = async () => {
    setSaving(true);
    try {
      await updateClient(id!, {
        ...editForm,
        email_to: typeof editForm.email_to === "string"
          ? (editForm.email_to as string).split(",").map(e => e.trim())
          : editForm.email_to,
      });
      toast("Cliente atualizado!", "success");
      setShowEditModal(false);
      load();
    } catch { toast("Erro ao salvar.", "error"); }
    finally { setSaving(false); }
  };

  const handleRotateKey = async () => {
    if (!confirm("Gerar nova API Key? A chave atual será invalidada.")) return;
    const data = await rotateKey(id!);
    setRotatedKey(data.api_key);
    load();
  };

  const handleRestartAgent = async () => {
    if (!confirm("Solicitar reinício do agente? Ele será reiniciado no próximo ping (até 5 min).")) return;
    try {
      await restartAgent(id!);
      toast("Reinício agendado! O agente será reiniciado no próximo ping.", "success");
    } catch {
      toast("Erro ao solicitar reinício.", "error");
    }
  };

  const isAgentOnline = client && client.active &&
    (client.last_seen && new Date().getTime() - new Date(client.last_seen).getTime() < 15 * 60 * 1000);

  const copyText = (t: string) => { navigator.clipboard.writeText(t); toast("Copiado!", "success"); };

  if (loading) return <div className="loading-state"><div className="spinner" /></div>;
  if (!client) return <div className="empty-state">Cliente não encontrado.</div>;

  return (
    <>
      <div className="page-header">
        <div className="flex items-center gap-3">
          <button className="btn-icon" onClick={() => navigate("/clients")}><ArrowLeft size={16} /></button>
          <div>
            <h1 className="page-title">{client.name}</h1>
            <p className="page-subtitle flex items-center gap-2">
              <StatusBadge status={client.last_backup_status} />
              {client.last_backup_at && `Último backup: ${fmtDate(client.last_backup_at)}`}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary" onClick={() => { setEditForm({ ...client, email_to: (client.email_to || []).join(", ") as unknown as string[] }); setShowEditModal(true); }}>
            <Edit2 size={15} /> Editar
          </button>
          <button className="btn btn-secondary" onClick={handleRotateKey}>
            <RefreshCw size={15} /> Rodar API Key
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleRestartAgent}
            title={!isAgentOnline ? "Agente offline — o reinício será executado no próximo ping" : "Reiniciar o agente Windows"}
          >
            <RotateCcw size={15} /> Reiniciar Agent
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="card mb-4">
        <div className="detail-grid">
          <div className="detail-item">
            <span className="detail-label">Client ID</span>
            <div className="flex items-center gap-2">
              <span className="detail-value font-mono text-sm">{client.id}</span>
              <button className="btn-icon" onClick={() => copyText(client.id)}><Copy size={12} /></button>
            </div>
          </div>
          <div className="detail-item">
            <span className="detail-label">API Key (prefixo)</span>
            <span className="detail-value font-mono text-sm">{client.api_key_prefix}…</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Horário do Backup</span>
            <span className="detail-value">
              {String(client.backup_hour).padStart(2,"0")}:{String(client.backup_minute).padStart(2,"0")}
            </span>
          </div>
          <div className="detail-item">
            <span className="detail-label">E-mails</span>
            <span className="detail-value text-sm">{(client.email_to || []).join(", ") || "—"}</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Criado em</span>
            <span className="detail-value">{fmtDate(client.created_at)}</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Status do Agente</span>
            <StatusBadge status={client.active ? "ONLINE" : "DESATIVADO"} />
          </div>
        </div>
      </div>

      {/* NVRs */}
      <div className="flex items-center justify-between mb-3">
        <div className="section-title mb-0"><Server size={15} />NVRs ({nvrs.length})</div>
        <button className="btn btn-secondary" onClick={() => setShowNVRModal(true)}>
          <Plus size={14} /> Adicionar NVR
        </button>
      </div>

      {nvrs.length === 0 ? (
        <div className="empty-state" style={{ padding: "32px" }}>
          <div className="empty-icon">📹</div>
          <div>Nenhum NVR cadastrado.</div>
        </div>
      ) : (
        <div className="table-wrap mb-6">
          <table>
            <thead><tr><th>Nome</th><th>IP</th><th>Usuário</th><th>Ações</th></tr></thead>
            <tbody>
              {nvrs.map(nvr => (
                <tr key={nvr.id}>
                  <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{nvr.name}</td>
                  <td className="font-mono text-sm">{nvr.ip}</td>
                  <td className="text-secondary">{nvr.username}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button className="btn btn-secondary btn-sm"
                        onClick={() => setShowRecordingModal({show: true, nvrName: nvr.name, cameras: nvr.last_recording_status || []})}>
                        Status de Gravação
                      </button>
                      <button className="btn-icon" style={{ color: "var(--err)" }}
                        onClick={() => handleDeleteNVR(nvr.id, nvr.name)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Backup history */}
      <div className="section-title"><Archive size={15} />Histórico de Backups</div>
      {backups.length === 0 ? (
        <div className="empty-state" style={{ padding: "32px" }}>
          <div className="empty-icon">📦</div>
          <div>Nenhum backup realizado ainda.</div>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Data/Hora</th><th>Status</th><th>Origem</th><th>ZIP</th><th>Email</th></tr></thead>
            <tbody>
              {backups.map(b => (
                <tr key={b.id}>
                  <td className="text-sm">{fmtDate(b.started_at)}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td className="text-secondary text-sm">{b.trigger}</td>
                  <td className="text-secondary text-sm">
                    {b.zip_size ? `${(b.zip_size / 1024 / 1024).toFixed(1)} MB` : "—"}
                  </td>
                  <td>{b.email_sent ? "✅" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* NVR Modal */}
      {showNVRModal && (
        <Modal title="Adicionar NVR" onClose={() => setShowNVRModal(false)}>
          {(["name","ip","username","password"] as const).map(f => (
            <div className="form-group" key={f}>
              <label className="form-label">
                {f === "name" ? "Nome" : f === "ip" ? "Endereço IP" : f === "username" ? "Usuário" : "Senha"}
              </label>
              <input className="form-input" type={f === "password" ? "password" : "text"}
                placeholder={f === "name" ? "NVR_Loja1" : f === "ip" ? "192.168.1.100" : ""}
                value={nvrForm[f]} onChange={e => setNvrForm({ ...nvrForm, [f]: e.target.value })} />
            </div>
          ))}
          <div className="flex gap-3 mt-4" style={{ justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setShowNVRModal(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleAddNVR} disabled={saving}>
              {saving ? <span className="spinner spinner-sm" /> : <><Plus size={15} /> Adicionar</>}
            </button>
          </div>
        </Modal>
      )}

      {/* Edit Modal */}
      {showEditModal && (
        <Modal title="Editar Cliente" onClose={() => setShowEditModal(false)}>
          <div className="form-group">
            <label className="form-label">Nome</label>
            <input className="form-input" value={editForm.name || ""}
              onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
          </div>
          <div className="flex gap-3">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Hora</label>
              <input className="form-input" type="number" min={0} max={23} value={editForm.backup_hour ?? 2}
                onChange={e => setEditForm({ ...editForm, backup_hour: +e.target.value })} />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Minuto</label>
              <input className="form-input" type="number" min={0} max={59} value={editForm.backup_minute ?? 0}
                onChange={e => setEditForm({ ...editForm, backup_minute: +e.target.value })} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">E-mails (separados por vírgula)</label>
            <input className="form-input" value={editForm.email_to as unknown as string || ""}
              onChange={e => setEditForm({ ...editForm, email_to: e.target.value as unknown as string[] })} />
          </div>
          <div className="form-group">
            <label className="form-label">Nova senha do ZIP (vazio = manter atual)</label>
            <input className="form-input" type="password" value={editForm.zip_password || ""}
              onChange={e => setEditForm({ ...editForm, zip_password: e.target.value })} />
          </div>
          <div className="flex gap-3 mt-4" style={{ justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setShowEditModal(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleEditSave} disabled={saving}>
              {saving ? <span className="spinner spinner-sm" /> : "Salvar"}
            </button>
          </div>
        </Modal>
      )}

      {/* Rotated key modal */}
      {rotatedKey && (
        <Modal title="Nova API Key gerada" onClose={() => setRotatedKey(null)}>
          <div style={{ background: "var(--warn-bg)", border: "1px solid rgba(245,158,11,0.3)",
            borderRadius: "var(--radius-sm)", padding: "12px 16px", marginBottom: 20,
            color: "var(--warn)", fontSize: 13 }}>
            ⚠️ Copie agora. Não será exibida novamente. Atualize o agent.conf no cliente.
          </div>
          <div className="api-key-display" style={{ borderColor: "rgba(245,158,11,0.4)" }}>
            <span className="api-key-value" style={{ color: "var(--warn)" }}>{rotatedKey}</span>
            <button className="btn-icon" onClick={() => copyText(rotatedKey)}><Copy size={14} /></button>
          </div>
          <button className="btn btn-primary mt-4 w-full" style={{ justifyContent: "center" }}
            onClick={() => setRotatedKey(null)}>Entendi</button>
        </Modal>
      )}
      {/* Recording Status Modal */}
      {showRecordingModal.show && (
        <Modal wide={true} title={`Gravação - ${showRecordingModal.nvrName} (${fmtDate(client.last_backup_at)})`} onClose={() => setShowRecordingModal({show: false, nvrName: "", cameras: []})}>
          {showRecordingModal.cameras.length === 0 ? (
             <div className="empty-state">Sem dados de gravação disponíveis.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Câmera</th>
                    <th>Status</th>
                    <th>Dias Gravados</th>
                    <th>Mapa (15 dias)</th>
                  </tr>
                </thead>
                <tbody>
                  {showRecordingModal.cameras.map((cam, i) => (
                    <tr key={i}>
                      <td>{cam.nome}</td>
                      <td>
                        <StatusBadge status={cam.online ? (cam.total_dias > 0 ? "ONLINE" : "ERROR") : "OFFLINE"} />
                      </td>
                      <td>{cam.total_dias}/15</td>
                      <td style={{ letterSpacing: "1px" }}>
                        <MiniCalendar mapStr={cam.mapa} referenceDate={client.last_backup_at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

