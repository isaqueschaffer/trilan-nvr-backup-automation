interface Props { status: string | null | undefined; }

const map: Record<string, { cls: string; dot: string; label: string }> = {
  OK:      { cls: "ok",   dot: "ok",   label: "OK" },
  PARTIAL: { cls: "warn", dot: "warn", label: "Parcial" },
  PARCIAL: { cls: "warn", dot: "warn", label: "Parcial" },
  ERROR:   { cls: "err",  dot: "err",  label: "Erro" },
  ERRO:    { cls: "err",  dot: "err",  label: "Erro" },
};

export default function StatusBadge({ status }: Props) {
  const cfg = map[status || ""] || { cls: "muted", dot: "", label: status || "—" };
  return (
    <span className={`badge ${cfg.cls}`}>
      {cfg.dot && <span className={`dot ${cfg.dot}`} />}
      {cfg.label}
    </span>
  );
}
