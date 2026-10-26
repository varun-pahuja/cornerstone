import { useEffect, useRef, useState } from "react";
import { CameraOff } from "lucide-react";

/**
 * Refreshes an <img> from the bounded JPEG endpoint while the camera runs.
 * Self-contained: its polling state never touches dashboard state (the frame
 * feed stays isolated from app-wide renders).
 *
 * Renders NOTHING decorative when disconnected — the empty state names the
 * situation instead of faking a preview.
 */
export function FramePreview({
  active,
  hint,
  className,
  badge,
}: {
  active: boolean;
  hint?: React.ReactNode;
  className?: string;
  badge?: React.ReactNode;
}) {
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
      <div
        className={`relative flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-line-strong bg-rail ${className ?? ""}`}
      >
        <span className="absolute top-3 left-3 z-10">
          <span className="label rounded-sm border border-line bg-panel/80 px-2 py-1">
            no signal
          </span>
        </span>
        <CameraOff size={28} className="text-ink-faint" aria-hidden />
        <div className="max-w-[42ch] px-6 text-center">
          <p className="text-[13px] text-ink-soft">Camera not connected</p>
          <div className="mt-1 text-[12px] leading-relaxed text-ink-faint">
            {hint ?? "Nothing is rendered until a real source produces frames. No placeholder video."}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-sm border border-line bg-black ${className ?? ""}`}
    >
      <span className="absolute top-3 left-3 z-10 flex items-center gap-1.5 rounded-sm border border-ok/30 bg-ok-soft px-2 py-1 font-mono text-[10.5px] font-medium tracking-[0.06em] text-ok uppercase">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" aria-hidden />
        live
      </span>
      {badge && <span className="absolute top-3 right-3 z-10">{badge}</span>}
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
      <span className="data absolute right-2 bottom-2 rounded-sm border border-line bg-panel/85 px-1.5 py-0.5 text-[10px] text-ink-faint">
        ~2.5 fps preview · recognition path gets every frame
      </span>
    </div>
  );
}
