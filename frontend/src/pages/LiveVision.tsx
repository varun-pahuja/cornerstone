import { useEffect, useRef, useState } from "react";
import { Camera, CameraOff, Plug, Square } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";

/** Refreshes an <img> from the bounded JPEG endpoint while the camera runs. */
function FramePreview({ active }: { active: boolean }) {
  const [tick, setTick] = useState(0);
  const [failedTick, setFailedTick] = useState(-1);
  const failed = failedTick === tick;
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setTick((t) => t + 1), 400);
    return () => clearInterval(id);
  }, [active]);

  if (!active) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 border border-dashed border-line bg-rail">
        <CameraOff size={32} className="text-ink-faint" aria-hidden />
        <div className="text-center">
          <p className="text-[13px] text-ink-soft">No camera connected</p>
          <p className="mt-1 text-[12px] text-ink-faint">
            Nothing is rendered until a real source produces frames. No placeholder video.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden border border-line bg-rail">
      {failed ? (
        <div className="text-center">
          <p className="text-[13px] text-ink-soft">Frame unavailable</p>
          <p className="mt-1 text-[12px] text-ink-faint">The preview endpoint returned no frame.</p>
        </div>
      ) : (
        <img
          ref={imgRef}
          key={tick}
          src={`/api/v1/camera/frame.jpg?ts=${tick}`}
          alt="Live camera frame"
          className="h-full w-full object-contain"
          onError={() => setFailedTick(tick)}
        />
      )}
      <span className="data absolute bottom-2 right-2 border border-line bg-panel/90 px-1.5 py-0.5 text-[10px] text-ink-soft">
        ~2.5 fps preview · recognition path gets every frame
      </span>
    </div>
  );
}

export default function LiveVision() {
  const cameras = usePoll(() => api.cameras(), 15_000);
  const camStatus = usePoll(() => api.cameraStatus(), 2_000);
  const caps = usePoll(() => api.cameraCapabilities(), 60_000);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const st = camStatus.data;
  const connected = st?.state === "CONNECTED";

  async function handleStart() {
    setMsg(null);
    setBusy(true);
    try {
      await api.cameraStart();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    } finally {
      setBusy(false);
      camStatus.refresh();
    }
  }

  async function handleStop() {
    setMsg(null);
    setBusy(true);
    try {
      await api.cameraStop();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    } finally {
      setBusy(false);
      camStatus.refresh();
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Live Vision</h1>
        <div className="flex items-center gap-2">
          {st && (
            <StatusBadge
              tone={connected ? "ok" : st.state === "ERROR" || st.state === "UNAVAILABLE" ? "danger" : "neutral"}
            >
              {st.state}
            </StatusBadge>
          )}
          {connected ? (
            <button
              type="button"
              onClick={handleStop}
              disabled={busy}
              className="inline-flex items-center gap-1.5 border border-danger/40 bg-danger-soft px-3 py-1.5 text-[13px] text-danger disabled:opacity-50"
            >
              <Square size={14} aria-hidden />
              Stop camera
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStart}
              disabled={busy}
              className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper disabled:opacity-50"
            >
              <Camera size={14} aria-hidden />
              {busy ? "Starting…" : "Start camera"}
            </button>
          )}
        </div>
      </div>

      {msg && (
        <div className="border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-warn" role="status">
          {msg}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Preview" className="lg:col-span-2">
          <FramePreview active={connected} />
        </Card>

        <div className="space-y-4">
          <Card title="Status">
            {st ? (
              <>
                <Row label="State" value={st.state} />
                <Row label="Provider" value={st.provider ?? "—"} />
                <Row
                  label="Resolution"
                  value={st.width && st.height ? `${st.width}×${st.height}` : "Unavailable"}
                />
                <Row label="FPS" value={st.fps ?? "Unavailable"} />
                <Row label="Frames captured" value={st.frames_captured} />
                <Row label="Stale frames dropped" value={st.frames_dropped} />
                <Row
                  label="Last frame age"
                  value={st.last_frame_age_ms !== null ? `${st.last_frame_age_ms} ms` : "Unavailable"}
                />
                {st.error && (
                  <Row label="Error" value={<span className="text-danger">{st.error}</span>} />
                )}
              </>
            ) : (
              <LoadError error={camStatus.error} loading={camStatus.loading} />
            )}
          </Card>

          <Card title="Source">
            {cameras.loading && !cameras.data ? (
              <LoadError error={cameras.error} loading />
            ) : (
              <ul className="space-y-1.5">
                {(cameras.data ?? []).map((c) => (
                  <li key={c.provider} className="flex items-start justify-between gap-2 text-[12px]">
                    <span className="text-ink-soft">
                      {c.label}
                      {c.device_path && (
                        <span className="data block text-ink-faint">{c.device_path}</span>
                      )}
                      {c.detail && <span className="block text-ink-faint">{c.detail}</span>}
                    </span>
                    <StatusBadge tone={c.available ? "ok" : "neutral"}>
                      {c.available ? "available" : "unavailable"}
                    </StatusBadge>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[11px] text-ink-faint">
              Switch sources under Device Settings → Camera; provider changes need a backend
              restart.
            </p>
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
