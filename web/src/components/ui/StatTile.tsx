import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Card } from "./Card";

function useCountUp(target: number, durationMs = 700) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return value;
}

export function StatTile({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: number;
  icon?: ReactNode;
  accent?: string;
}) {
  const animated = useCountUp(value);
  return (
    <Card className="flex items-center gap-4">
      <div
        className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0"
        style={{
          color: accent ?? "var(--color-accent)",
          backgroundColor: `${accent ?? "var(--color-accent)"}18`,
        }}
      >
        {icon}
      </div>
      <div>
        <div className="text-2xl font-semibold tabular-nums">{animated}</div>
        <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{label}</div>
      </div>
    </Card>
  );
}
