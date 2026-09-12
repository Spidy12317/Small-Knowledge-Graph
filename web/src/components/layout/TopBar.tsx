import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Cpu, Wifi, WifiOff } from "lucide-react";

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 20_000,
    retry: 1,
  });

  return (
    <header className="h-16 shrink-0 flex items-center justify-between px-8 border-b border-[var(--color-border-soft)] sticky top-0 z-20 glass">
      <div>
        <h1 className="text-base font-semibold text-[var(--color-text)]">{title}</h1>
        {subtitle && <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {data && (
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] border border-[var(--color-border)] rounded-full px-3 py-1.5">
            <Cpu size={13} />
            <span className="text-[var(--color-text)] font-medium">{data.llm.provider}</span>
            <span className="text-[var(--color-text-faint)]">/</span>
            <span className="font-mono text-[11px]">{data.llm.model}</span>
          </div>
        )}
        <div
          className="flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 border"
          style={{
            color: isError ? "var(--color-danger)" : "var(--color-success)",
            borderColor: isError ? "var(--color-danger)33" : "var(--color-success)33",
            backgroundColor: isError ? "var(--color-danger)0f" : "var(--color-success)0f",
          }}
        >
          {isError ? <WifiOff size={13} /> : <Wifi size={13} />}
          {isError ? "API offline" : "API connected"}
        </div>
      </div>
    </header>
  );
}
