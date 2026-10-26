import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
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
import { api } from "../../services/api";
import type { AppStatus, HealthResponse, SystemMetrics } from "../../types/api";
import { cn } from "../../lib/utils";
import { StatusBadge } from "../ui/StatusBadge";
import { Toaster } from "../ui/sonner";
import { TooltipProvider } from "../ui/tooltip";

const NAV = [
  {
    section: "Console",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/vision", label: "Live Vision", icon: Camera, end: false },
    ],
  },
  {
    section: "Intelligence",
    items: [
      { to: "/lab", label: "AI Lab", icon: FlaskConical, end: false },
      { to: "/dataset", label: "Dataset Studio", icon: Layers, end: false },
      { to: "/training", label: "Training Center", icon: GraduationCap, end: false },
    ],
  },
  {
    section: "System",
    items: [
      { to: "/history", label: "Recognition History", icon: History, end: false },
      { to: "/calibration", label: "Calibration", icon: Target, end: false },
      { to: "/settings", label: "Device Settings", icon: Settings, end: false },
      { to: "/health", label: "System Health", icon: Activity, end: false },
    ],
  },
] as const;

type ConnState = "checking" | "connected" | "disconnected";

/** Backend reachability — polled from the shell so every page inherits it. */
function useConnection(): { state: ConnState; version: string | null } {
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

  return { state, version };
}

function usePollValue<T>(fetcher: () => Promise<T>, intervalMs: number): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      fetcher()
        .then((v) => {
          if (alive) setValue(v);
        })
        .catch(() => undefined);
    load();
    const id = setInterval(load, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
    // oxlint-disable-next-line react-hooks/exhaustive-deps -- fetcher is an inline factory; only the interval is stable
  }, [intervalMs]);
  return value;
}

const runtimeTone = (s: AppStatus["runtime_state"]) =>
  s === "RUNNING" ? "primary" : s === "ERROR" ? "danger" : "neutral";

function SidebarFooter({ conn }: { conn: ReturnType<typeof useConnection> }) {
  const dot =
    conn.state === "connected"
      ? "bg-ok"
      : conn.state === "disconnected"
        ? "bg-danger"
        : "bg-ink-faint";
  return (
    <div className="border-t border-line-dark px-3 py-3 lg:px-4">
      <div className="flex items-center gap-2" title={`Backend ${conn.state}`}>
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dot)} aria-hidden />
        <span className="hidden font-mono text-[10.5px] tracking-[0.06em] text-ink-soft uppercase lg:inline">
          {conn.state === "connected"
            ? `Online · v${conn.version ?? "?"}`
            : conn.state === "disconnected"
              ? "Backend offline"
              : "Checking…"}
        </span>
      </div>
      <p className="mt-2 hidden text-[11px] leading-snug text-ink-faint lg:block">
        Offline-first · local runtime
      </p>
    </div>
  );
}

export function AppShell() {
  const conn = useConnection();
  const status = usePollValue<AppStatus>(() => api.status(), 10_000);
  const metrics = usePollValue<SystemMetrics>(() => api.systemMetrics(), 60_000);
  const { pathname } = useLocation();

  const crumb = NAV.flatMap((g) =>
    g.items.map((i) => ({ ...i, section: g.section })),
  ).find((i) => (i.end ? pathname === i.to : pathname.startsWith(i.to)));

  return (
    <TooltipProvider delay={250}>
      <div className="flex min-h-screen">
        {/* Navigation rail */}
        <nav
          aria-label="Main navigation"
          className="fixed inset-y-0 left-0 z-20 flex w-16 flex-col border-r border-line-dark bg-rail lg:w-60"
        >
          <div className="flex h-14 items-center justify-center border-b border-line-dark lg:justify-start lg:px-4">
            {/* Typographic wordmark — no invented symbol (docs/design_research.md) */}
            <span className="display text-[13.5px] font-semibold tracking-tight text-ink lg:text-[17px]">
              Silent<span className="text-primary">OS</span>
            </span>
          </div>

          <ul className="flex-1 space-y-4 overflow-y-auto px-2 py-3 lg:px-3">
            {NAV.map((group) => (
              <li key={group.section}>
                <p className="label mb-1 hidden px-2 lg:block">{group.section}</p>
                <ul className="space-y-0.5">
                  {group.items.map(({ to, label, icon: Icon, end }) => (
                    <li key={to}>
                      <NavLink
                        to={to}
                        end={end}
                        title={label}
                        className={({ isActive }) =>
                          cn(
                            "relative flex items-center justify-center gap-2.5 rounded-sm px-2 py-2 text-[13px] font-medium transition-colors lg:justify-start lg:px-2.5",
                            isActive
                              ? "bg-rail-hover text-ink shadow-[inset_2px_0_0_0_var(--color-primary)]"
                              : "text-ink-faint hover:bg-rail-hover hover:text-ink",
                          )
                        }
                      >
                        <Icon className="h-4 w-4 shrink-0" aria-hidden />
                        <span className="hidden lg:inline">{label}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>

          <SidebarFooter conn={conn} />
        </nav>

        {/* Content column */}
        <div className="flex min-w-0 flex-1 flex-col pl-16 lg:pl-60">
          {/* Top bar */}
          <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-4 border-b border-line bg-canvas/90 px-5 backdrop-blur lg:px-8">
            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[12px]">
              <span className="label hidden sm:inline">{crumb?.section ?? "SilentOS"}</span>
              <span className="hidden text-ink-faint sm:inline" aria-hidden>
                /
              </span>
              <span className="truncate font-medium text-ink-soft">
                {crumb?.label ?? "Not found"}
              </span>
            </nav>
            <div className="flex items-center gap-3">
              {status && (
                <StatusBadge tone={runtimeTone(status.runtime_state)}>
                  {status.runtime_state}
                </StatusBadge>
              )}
              <span className="data hidden text-[11.5px] text-ink-faint md:inline">
                {metrics?.hostname ?? ""}
              </span>
              {conn.state === "disconnected" && (
                <StatusBadge tone="danger">Backend offline</StatusBadge>
              )}
            </div>
          </header>

          <main className="flex-1">
            <div className="mx-auto w-full max-w-[1480px] px-5 py-5 lg:px-8 lg:py-6">
              <Outlet />
            </div>
          </main>
        </div>

        <Toaster position="bottom-right" />
      </div>
    </TooltipProvider>
  );
}
