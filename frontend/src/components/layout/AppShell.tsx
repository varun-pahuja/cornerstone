import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  Camera,
  FlaskConical,
  GraduationCap,
  History,
  Layers,
  LayoutDashboard,
  Settings,
  Target,
} from "lucide-react";
import { api, ApiError } from "../../services/api";
import type { HealthResponse } from "../../types/api";
import { cn } from "../../lib/utils";
import { StatusBadge } from "../ui/StatusBadge";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/vision", label: "Live Vision", icon: Camera, end: false },
  { to: "/lab", label: "AI Lab", icon: FlaskConical, end: false },
  { to: "/dataset", label: "Dataset Studio", icon: Layers, end: false },
  { to: "/training", label: "Training Center", icon: GraduationCap, end: false },
  { to: "/history", label: "Recognition History", icon: History, end: false },
  { to: "/calibration", label: "Calibration", icon: Target, end: false },
  { to: "/settings", label: "Device Settings", icon: Settings, end: false },
  { to: "/health", label: "System Health", icon: Activity, end: false },
] as const;

type ConnState = "checking" | "connected" | "disconnected";

function ConnectionPill() {
  const [state, setState] = useState<ConnState>("checking");
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const h: HealthResponse = await api.health();
        if (alive) {
          setState("connected");
          setVersion(h.version);
        }
      } catch {
        if (alive) {
          setState("disconnected");
          setVersion(null);
        }
      }
    };
    check();
    const id = setInterval(check, 10_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (state === "checking") return <StatusBadge tone="neutral">Checking…</StatusBadge>;
  if (state === "disconnected") return <StatusBadge tone="danger">Backend offline</StatusBadge>;
  return <StatusBadge tone="ok">Connected · v{version}</StatusBadge>;
}

export function AppShell() {
  return (
    <div className="flex min-h-screen">
      {/* Navigation rail */}
      <nav
        aria-label="Main navigation"
        className="fixed inset-y-0 left-0 z-20 flex w-14 flex-col border-r border-line-dark bg-rail md:w-56"
      >
        <div className="flex h-14 items-center border-b border-line-dark px-3 md:px-4">
          {/* Typographic wordmark — no invented symbol (see docs/design_research.md) */}
          <span className="text-[15px] font-semibold tracking-tight text-white">
            Silent<span className="text-teal-400">OS</span>
          </span>
        </div>
        <ul className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded px-2.5 py-2 text-[13px] font-medium transition-colors",
                    isActive
                      ? "bg-rail-hover text-white shadow-[inset_2px_0_0_0_var(--color-accent)]"
                      : "text-white/60 hover:bg-rail-hover hover:text-white/90",
                  )
                }
                title={label}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className="hidden md:inline">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="border-t border-line-dark p-3 text-[11px] text-white/40">
          <span className="hidden md:inline">Offline-first · local runtime</span>
          <span className="md:hidden">v0.1</span>
        </div>
      </nav>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col md:pl-56 pl-14">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-panel/90 px-4 backdrop-blur md:px-6">
          <span className="label">Assistive Communication Console</span>
          <ConnectionPill />
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export { ApiError };
