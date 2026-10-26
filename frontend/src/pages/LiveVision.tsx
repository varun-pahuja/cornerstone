import { useState } from "react";
import { Camera, CameraOff, Plug } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";

export default function LiveVision() {
  const cameras = usePoll(() => api.cameras(), 15_000);
  const camStatus = usePoll(() => api.cameraStatus(), 5_000);
  const caps = usePoll(() => api.cameraCapabilities(), 60_000);
  const [msg, setMsg] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");

  async function handleStart() {
    setMsg(null);
    try {
      await api.cameraStart();
      camStatus.refresh();
    } catch (err) {
      // Backend refuses honestly until Phase 3 — show its exact reason.
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    }
  }

  const st = camStatus.data;
  const available = (cameras.data ?? []).filter((c) => c.available);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Live Vision</h1>
        <div className="flex items-center gap-2">
          {st && (
            <StatusBadge tone={st.state === "CONNECTED" ? "ok" : "neutral"}>{st.state}</StatusBadge>
          )}
          <button
            type="button"
            onClick={handleStart}
            className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper"
          >
            <Camera size={14} aria-hidden />
            Start camera
          </button>
        </div>
      </div>

      {msg && (
        <div className="border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-warn" role="status">
          {msg}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Preview" className="lg:col-span-2">
          <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 border border-dashed border-line bg-rail">
            <CameraOff size={32} className="text-ink-faint" aria-hidden />
            {st?.state === "CONNECTED" ? (
              <p className="text-[13px] text-ink-soft">
                Connected — frame preview streams here once Phase 3 delivers frames.
              </p>
            ) : (
              <div className="text-center">
                <p className="text-[13px] text-ink-soft">No camera connected</p>
                <p className="mt-1 text-[12px] text-ink-faint">
                  Nothing is rendered until a real source produces frames. No placeholder video.
                </p>
              </div>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Status">
            {st ? (
              <>
                <Row label="State" value={st.state} />
                <Row label="Provider" value={st.provider} />
                <Row label="Resolution" value={st.width && st.height ? `${st.width}×${st.height}` : "Unavailable"} />
                <Row label="FPS" value={st.fps ?? "Unavailable"} />
                <Row label="Frames captured" value={st.frames_captured} />
                <Row
                  label="Last frame age"
                  value={st.last_frame_age_ms !== null ? `${st.last_frame_age_ms} ms` : "Unavailable"}
                />
                {st.error && <Row label="Error" value={<span className="text-danger">{st.error}</span>} />}
              </>
            ) : (
              <LoadError error={camStatus.error} loading={camStatus.loading} />
            )}
          </Card>

          <Card title="Source">
            {cameras.loading && !cameras.data ? (
              <LoadError error={cameras.error} loading />
            ) : (
              <div className="space-y-3">
                <select
                  className="w-full border border-line bg-paper px-2.5 py-1.5 text-[13px]"
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  <option value="">Select a source…</option>
                  {available.map((c) => (
                    <option key={c.provider} value={c.provider}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <ul className="space-y-1.5">
                  {(cameras.data ?? []).map((c) => (
                    <li key={c.provider} className="flex items-start justify-between gap-2 text-[12px]">
                      <span className="text-ink-soft">
                        {c.label}
                        {c.device_path && <span className="data block text-ink-faint">{c.device_path}</span>}
                        {c.detail && <span className="block text-ink-faint">{c.detail}</span>}
                      </span>
                      <StatusBadge tone={c.available ? "ok" : "neutral"}>
                        {c.available ? "available" : "unavailable"}
                      </StatusBadge>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </div>
      </div>

      <Card title="Device capabilities (kernel-reported)">
        {caps.data ? (
          caps.data.v4l2_devices.length > 0 ? (
            <ul className="space-y-1.5">
              {caps.data.v4l2_devices.map((d) => (
                <li key={d.device_path} className="flex items-center gap-2 text-[13px]">
                  <Plug size={13} className="text-ink-faint" aria-hidden />
                  <span className="data">{d.device_path}</span>
                  <span className="text-ink-soft">{d.name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty text="No V4L2 video devices detected on this machine." />
          )
        ) : (
          <LoadError error={caps.error} loading={caps.loading} />
        )}
        <p className="mt-2 text-[12px] text-ink-faint">{caps.data?.note}</p>
      </Card>
    </div>
  );
}
