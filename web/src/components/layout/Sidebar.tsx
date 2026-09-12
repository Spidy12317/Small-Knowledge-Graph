import { NavLink } from "react-router-dom";
import clsx from "clsx";
import {
  LayoutDashboard,
  Waypoints,
  Sparkles,
  SearchCode,
  SlidersHorizontal,
  GitBranch,
} from "lucide-react";
import { GraphSwitcher } from "./GraphSwitcher";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/explore", label: "Explore", icon: Waypoints },
  { to: "/build", label: "Build", icon: Sparkles },
  { to: "/steps", label: "Steps", icon: GitBranch },
  { to: "/query", label: "Query", icon: SearchCode },
  { to: "/settings", label: "Settings", icon: SlidersHorizontal },
];

export function Sidebar() {
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 border-r border-[var(--color-border-soft)] flex flex-col">
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-[var(--color-border-soft)]">
        <svg width="22" height="22" viewBox="0 0 32 32" className="shrink-0">
          <circle cx="16" cy="7" r="3.4" fill="var(--color-central)" />
          <circle cx="6" cy="24" r="3" fill="var(--color-data)" />
          <circle cx="26" cy="24" r="3" fill="var(--color-category)" />
          <path
            d="M16 10 L7 21 M16 10 L25 21"
            stroke="#4b4f66"
            strokeWidth="1.6"
            fill="none"
          />
        </svg>
        <div>
          <div className="text-sm font-semibold leading-none">SKG</div>
          <div className="text-[10px] text-[var(--color-text-faint)] mt-0.5 tracking-wide">
            Semantic Knowledge Graph
          </div>
        </div>
      </div>

      <GraphSwitcher />

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                isActive
                  ? "bg-[var(--color-accent)]/12 text-[var(--color-text)] shadow-[inset_0_0_0_1px_rgba(124,108,242,0.25)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.03]",
              )
            }
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-[var(--color-border-soft)] text-[10px] text-[var(--color-text-faint)] leading-relaxed">
        LLM-guided hierarchical graph
        <br />
        build &amp; retrieval engine.
      </div>
    </aside>
  );
}
