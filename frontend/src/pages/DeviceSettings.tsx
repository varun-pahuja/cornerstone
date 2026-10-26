import { useEffect, useState } from "react";
import { Save, TriangleAlert } from "lucide-react";
import { api, ApiError } from "../services/api";
import { Card, LoadError } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { RecognitionMode, SettingsUpdate, SettingsView } from "../types/api";

const PROVIDERS = ["video_file", "mock", "development_webcam", "pi_camera", "pi_usb_webcam"];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-ink-faint">{hint}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded-sm border border-line bg-elevated px-2.5 py-1.5 text-[13px] text-ink outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

export default function DeviceSettings() {
  const [form, setForm] = useState<SettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    api
      .getSettings()
      .then(setForm)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Backend unreachable"));
  }, []);

  function patch<K extends keyof SettingsView>(key: K, value: SettingsView[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
    setSaved(false);
  }

  function num(key: keyof SettingsView, value: string): void {
    const n = Number(value);
    if (!Number.isNaN(n)) patch(key, n as SettingsView[typeof key]);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const body: SettingsUpdate = {
      recognition_mode: form.recognition_mode,
      min_confidence: form.min_confidence,
      sign_threshold: form.sign_threshold,
      lip_threshold: form.lip_threshold,
      allow_single_modality: form.allow_single_modality,
      speech_enabled: form.speech_enabled,
      speech_cooldown_ms: form.speech_cooldown_ms,
      history_retention_days: form.history_retention_days,
      history_max_entries: form.history_max_entries,
      camera_provider: form.camera_provider,
      camera_target_width: form.camera_target_width,
      camera_target_height: form.camera_target_height,
      camera_target_fps: form.camera_target_fps,
      camera_video_path: form.camera_video_path,
      camera_device_index: form.camera_device_index,
    };
    try {
      const updated = await api.updateSettings(body);
      setForm(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Backend unreachable");
    } finally {
      setSaving(false);
    }
  }

  if (error && !form) return <LoadError error={error} loading={false} />;
  if (!form) return <LoadError error={null} loading />;

  return (
    <form onSubmit={save} className="space-y-4">
      <PageHeader
        title="Device Settings"
        description="Runtime, camera, speech, and retention configuration — validated server-side on save."
        actions={
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-sm border border-primary/50 bg-primary-soft px-3 py-1.5 text-[13px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
          >
            <Save size={14} aria-hidden />
            {saving ? "Saving…" : "Save settings"}
          </button>
        }
      />

      {error && (
        <div className="rounded-sm border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger" role="alert">
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-sm border border-ok/30 bg-ok-soft px-3 py-2 text-[13px] text-ok" role="status">
          Settings saved.
        </div>
      )}
      {form.requires_restart.length > 0 && (
        <div className="flex items-start gap-2 rounded-sm border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-warn">
          <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden />
          <span>
            Saved, but these changes only take effect after a backend restart:{" "}
            <span className="data">{form.requires_restart.join(", ")}</span>
          </span>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Recognition">
          <div className="space-y-3">
            <Field label="Mode">
              <select
                className={inputCls}
                value={form.recognition_mode}
                onChange={(e) => patch("recognition_mode", e.target.value as RecognitionMode)}
              >
                <option value="sign">sign — gesture only</option>
                <option value="lip">lip — silent-lip only</option>
                <option value="both">both — fused</option>
              </select>
            </Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Sign threshold" hint="0–1">
                <input
                  type="number" step="0.01" min="0" max="1" className={inputCls}
                  value={form.sign_threshold}
                  onChange={(e) => num("sign_threshold", e.target.value)}
                />
              </Field>
              <Field label="Lip threshold" hint="0–1">
                <input
                  type="number" step="0.01" min="0" max="1" className={inputCls}
                  value={form.lip_threshold}
                  onChange={(e) => num("lip_threshold", e.target.value)}
                />
              </Field>
              <Field label="Min confidence" hint="0–1">
                <input
                  type="number" step="0.01" min="0" max="1" className={inputCls}
                  value={form.min_confidence}
                  onChange={(e) => num("min_confidence", e.target.value)}
                />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={form.allow_single_modality}
                onChange={(e) => patch("allow_single_modality", e.target.checked)}
              />
              Allow single-modality decisions (no fusion required)
            </label>
          </div>
        </Card>

        <Card title="Speech output">
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={form.speech_enabled}
                onChange={(e) => patch("speech_enabled", e.target.checked)}
              />
              Speak accepted messages (requires espeak-ng — Phase 8)
            </label>
            <Field label="Cooldown (ms)" hint="min gap between spoken messages">
              <input
                type="number" min="0" max="60000" step="100" className={inputCls}
                value={form.speech_cooldown_ms}
                onChange={(e) => num("speech_cooldown_ms", e.target.value)}
              />
            </Field>
          </div>
        </Card>

        <Card title="History retention">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Retention (days)">
              <input
                type="number" min="1" max="3650" className={inputCls}
                value={form.history_retention_days}
                onChange={(e) => num("history_retention_days", e.target.value)}
              />
            </Field>
            <Field label="Max entries">
              <input
                type="number" min="100" max="1000000" className={inputCls}
                value={form.history_max_entries}
                onChange={(e) => num("history_max_entries", e.target.value)}
              />
            </Field>
          </div>
        </Card>

        <Card title="Camera">
          <div className="space-y-3">
            <Field label="Provider" hint="Provider changes require a backend restart">
              <select
                className={inputCls}
                value={form.camera_provider}
                onChange={(e) => patch("camera_provider", e.target.value)}
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Width">
                <input
                  type="number" min="64" max="3840" className={inputCls}
                  value={form.camera_target_width}
                  onChange={(e) => num("camera_target_width", e.target.value)}
                />
              </Field>
              <Field label="Height">
                <input
                  type="number" min="64" max="2160" className={inputCls}
                  value={form.camera_target_height}
                  onChange={(e) => num("camera_target_height", e.target.value)}
                />
              </Field>
              <Field label="FPS">
                <input
                  type="number" min="0.1" max="60" step="0.5" className={inputCls}
                  value={form.camera_target_fps}
                  onChange={(e) => num("camera_target_fps", e.target.value)}
                />
              </Field>
            </div>
            <Field label="Video path" hint="for the video_file provider — leave empty for none">
              <input
                type="text" className={inputCls}
                value={form.camera_video_path ?? ""}
                onChange={(e) => patch("camera_video_path", e.target.value || null)}
              />
            </Field>
            <Field label="Device index">
              <input
                type="number" min="0" max="16" className={inputCls}
                value={form.camera_device_index}
                onChange={(e) => num("camera_device_index", e.target.value)}
              />
            </Field>
          </div>
        </Card>
      </div>

      <Card title="Vocabulary (canonical, read-only)">
        <div className="flex flex-wrap gap-1.5">
          {form.vocabulary.map((v) => (
            <span key={v} className="data border border-line px-2 py-1 text-[12px]">
              {v}
            </span>
          ))}
          <span className="data border border-warn/40 bg-warn-soft px-2 py-1 text-[12px] text-warn">
            {form.abstain_label} (abstain)
          </span>
        </div>
        <p className="mt-2 text-[12px] text-ink-faint">
          One canonical mapping for both modalities — enforced in config, not editable per page.
        </p>
      </Card>

      <div className="flex items-center gap-2">
        <StatusBadge tone="neutral">API schema {form.vocabulary.length ? "1.0" : "?"}</StatusBadge>
        <span className="text-[12px] text-ink-faint">
          All fields validated server-side; invalid values return 422 and are not saved.
        </span>
      </div>
    </form>
  );
}
