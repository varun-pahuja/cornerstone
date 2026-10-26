import { useState } from "react";
import { Camera, Database, Download, FileVideo, PackageOpen, Play, Split, Wrench } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { ClipRecord, SplitResult, ValidationReport } from "../types/api";

const inputCls =
  "w-full border border-line bg-paper px-2.5 py-1.5 text-[13px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

function ResultBanner({ result, error }: { result: ClipRecord | null; error: string | null }) {
  if (error)
    return (
      <div className="border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger" role="alert">
        {error}
      </div>
    );
  if (result)
    return (
      <div className="border border-ok/30 bg-ok-soft px-3 py-2 text-[13px] text-ok" role="status">
        Registered <span className="data">{result.clip_id}</span> · {result.label} ·{" "}
        {result.frames} frames · {result.duration_s}s · sha {result.sha256.slice(0, 12)}…
      </div>
    );
  return null;
}

export default function DatasetStudio() {
  const stats = usePoll(() => api.datasetStats(), 10_000);
  const datasets = usePoll(() => api.datasets(), 15_000);
  const settings = usePoll(() => api.getSettings(), 60_000);
  const camera = usePoll(() => api.cameraStatus(), 3_000);
  const vocab = settings.data?.vocabulary ?? [];

  const [recordMsg, setRecordMsg] = useState<{ clip: ClipRecord | null; err: string | null } | null>(null);
  const [importMsg, setImportMsg] = useState<{ clip: ClipRecord | null; err: string | null } | null>(null);
  const [recording, setRecording] = useState(false);
  const [importing, setImporting] = useState(false);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [reportErr, setReportErr] = useState<string | null>(null);
  const [splitResult, setSplitResult] = useState<SplitResult | null>(null);
  const [splitErr, setSplitErr] = useState<string | null>(null);
  const [seed, setSeed] = useState(42);

  // record form
  const [rLabel, setRLabel] = useState("");
  const [rModality, setRModality] = useState<"sign" | "lip">("sign");
  const [rParticipant, setRParticipant] = useState("");
  const [rSession, setRSession] = useState("");
  const [rSeconds, setRSeconds] = useState(3);
  // import form
  const [iFile, setIFile] = useState<File | null>(null);
  const [iLabel, setILabel] = useState("");
  const [iModality, setIModality] = useState<"sign" | "lip">("sign");
  const [iParticipant, setIParticipant] = useState("");
  const [iSession, setISession] = useState("");

  // derive the effective label (first vocabulary entry until the user picks)
  const rLabelValue = rLabel || vocab[0] || "";
  const iLabelValue = iLabel || vocab[0] || "";

  const camConnected = camera.data?.state === "CONNECTED";
  const s = stats.data;
  const clipErr = (e: unknown): string => (e instanceof ApiError ? e.message : "Backend unreachable");

  async function handleRecord() {
    setRecording(true);
    setRecordMsg(null);
    try {
      const clip = await api.recordClip({
        seconds: rSeconds,
        meta: {
          label: rLabelValue, modality: rModality,
          participant_id: rParticipant || "default", session_id: rSession || "s1",
        },
      });
      setRecordMsg({ clip, err: null });
      stats.refresh();
    } catch (e) {
      setRecordMsg({ clip: null, err: clipErr(e) });
    } finally {
      setRecording(false);
    }
  }

  async function handleImport() {
    if (!iFile) return;
    setImporting(true);
    setImportMsg(null);
    try {
      const form = new FormData();
      form.append("file", iFile);
      form.append("label", iLabelValue);
      form.append("modality", iModality);
      form.append("participant_id", iParticipant || "default");
      form.append("session_id", iSession || "s1");
      const clip = await api.importClip(form);
      setImportMsg({ clip, err: null });
      stats.refresh();
    } catch (e) {
      setImportMsg({ clip: null, err: clipErr(e) });
    } finally {
      setImporting(false);
    }
  }

  async function handleValidate() {
    setReport(null);
    setReportErr(null);
    try {
      setReport(await api.validateDataset("default"));
    } catch (e) {
      setReportErr(clipErr(e));
    }
  }

  async function handleSplits() {
    setSplitResult(null);
    setSplitErr(null);
    try {
      const r = await api.generateSplits("default", { seed });
      setSplitResult(r);
      stats.refresh();
    } catch (e) {
      setSplitErr(clipErr(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Dataset Studio</h1>
        <div className="flex gap-2">
          <a
            href={api.exportUrl("default")}
            className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper"
            title="Download manifest + splits + clips as a zip"
          >
            <Download size={14} aria-hidden />
            Export zip
          </a>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Clips">
          {s ? <p className="data text-3xl font-semibold">{s.total_clips}</p> : <LoadError error={stats.error} loading={stats.loading} />}
          <p className="mt-1 text-[12px] text-ink-faint">counted from manifests on disk</p>
        </Card>
        <Card title="Raw video files">
          {s ? <p className="data text-3xl font-semibold">{s.raw_video_files}</p> : <LoadError error={stats.error} loading={stats.loading} />}
          <p className="mt-1 text-[12px] text-ink-faint">under data/raw, any session folder</p>
        </Card>
        <Card title="Splits">
          {s ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {Object.keys(s.by_split).length === 0 ? (
                <span className="text-[13px] text-ink-faint">None yet</span>
              ) : (
                Object.entries(s.by_split).map(([k, v]) => (
                  <span key={k} className="data border border-line px-1.5 py-0.5 text-[11px]">
                    {k}: {v}
                  </span>
                ))
              )}
            </div>
          ) : (
            <LoadError error={stats.error} loading={stats.loading} />
          )}
          <p className="mt-2 text-[12px] text-ink-faint">participant-based, generated below</p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Record from camera"
          actions={
            <StatusBadge tone={camConnected ? "ok" : "neutral"}>
              {camConnected ? "camera live" : camera.data?.state ?? "…"}
            </StatusBadge>
          }
        >
          <div className="space-y-3">
            {!camConnected && (
              <p className="text-[12px] text-ink-faint">
                Start a camera on Live Vision first — recording needs a running source.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Label">
                <select className={inputCls} value={rLabelValue} onChange={(e) => setRLabel(e.target.value)}>
                  {vocab.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </Field>
              <Field label="Modality">
                <select className={inputCls} value={rModality} onChange={(e) => setRModality(e.target.value as "sign" | "lip")}>
                  <option value="sign">sign</option>
                  <option value="lip">lip</option>
                </select>
              </Field>
              <Field label="Participant ID">
                <input className={inputCls} value={rParticipant} placeholder="e.g. p01"
                  onChange={(e) => setRParticipant(e.target.value)} />
              </Field>
              <Field label="Session ID">
                <input className={inputCls} value={rSession} placeholder="e.g. s1"
                  onChange={(e) => setRSession(e.target.value)} />
              </Field>
            </div>
            <Field label={`Duration: ${rSeconds}s`}>
              <input type="range" min={0.5} max={10} step={0.5} className="w-full"
                value={rSeconds} onChange={(e) => setRSeconds(Number(e.target.value))} />
            </Field>
            <button
              type="button"
              onClick={handleRecord}
              disabled={!camConnected || recording}
              className="inline-flex items-center gap-1.5 border border-accent bg-accent px-3 py-1.5 text-[13px] text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play size={14} aria-hidden />
              {recording ? `Recording ${rSeconds}s…` : `Record ${rSeconds}s clip`}
            </button>
            <ResultBanner result={recordMsg?.clip ?? null} error={recordMsg?.err ?? null} />
          </div>
        </Card>

        <Card title="Import a clip file">
          <div className="space-y-3">
            <input
              type="file"
              accept=".mp4,.mov,.webm,.avi,.mkv"
              onChange={(e) => setIFile(e.target.files?.[0] ?? null)}
              className="block w-full text-[13px] file:mr-3 file:border file:border-line file:bg-paper file:px-2 file:py-1 file:text-[12px]"
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Label">
                <select className={inputCls} value={iLabelValue} onChange={(e) => setILabel(e.target.value)}>
                  {vocab.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </Field>
              <Field label="Modality">
                <select className={inputCls} value={iModality} onChange={(e) => setIModality(e.target.value as "sign" | "lip")}>
                  <option value="sign">sign</option>
                  <option value="lip">lip</option>
                </select>
              </Field>
              <Field label="Participant ID">
                <input className={inputCls} value={iParticipant} placeholder="e.g. p02"
                  onChange={(e) => setIParticipant(e.target.value)} />
              </Field>
              <Field label="Session ID">
                <input className={inputCls} value={iSession} placeholder="e.g. s1"
                  onChange={(e) => setISession(e.target.value)} />
              </Field>
            </div>
            <button
              type="button"
              onClick={handleImport}
              disabled={!iFile || importing}
              className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50"
            >
              <PackageOpen size={14} aria-hidden />
              {importing ? "Importing…" : "Import clip"}
            </button>
            <ResultBanner result={importMsg?.clip ?? null} error={importMsg?.err ?? null} />
            <p className="text-[11px] text-ink-faint">
              Server validates: decodable, 0.2–30s, label in vocabulary, safe participant/session
              names. Files land under data/raw/ and are SHA-256 recorded.
            </p>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card
          title="Validation"
          actions={
            <button
              type="button"
              onClick={handleValidate}
              className="inline-flex items-center gap-1.5 border border-line px-2 py-1 text-[12px] hover:bg-paper"
            >
              <Wrench size={12} aria-hidden /> Run
            </button>
          }
        >
          {reportErr && <p className="text-[13px] text-danger">{reportErr}</p>}
          {report ? (
            <div className="space-y-2">
              <Row label="Checked" value={report.checked} />
              <Row label="Valid" value={<span className="text-ok">{report.valid}</span>} />
              <Row
                label="Invalid"
                value={<span className={report.invalid > 0 ? "text-danger" : ""}>{report.invalid}</span>}
              />
              {report.issues.length > 0 && (
                <ul className="space-y-1 pt-1">
                  {report.issues.map((i) => (
                    <li key={i.clip_id} className="text-[12px]">
                      <span className="data text-ink-faint">{i.file}</span>
                      {[...i.errors.map((e) => <span key={e} className="text-danger"> {e}</span>),
                        ...i.warnings.map((w) => <span key={w} className="text-warn"> {w}</span>)]}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : !reportErr ? (
            <Empty text="Not validated yet — run a check over every registered clip." />
          ) : null}
        </Card>

        <Card title="Participant splits">
          <div className="space-y-3">
            <div className="flex items-end gap-2">
              <Field label="Seed">
                <input type="number" min={0} className={inputCls} value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))} />
              </Field>
              <button
                type="button"
                onClick={handleSplits}
                className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper"
              >
                <Split size={14} aria-hidden />
                Generate
              </button>
            </div>
            {splitErr && <p className="text-[13px] text-danger">{splitErr}</p>}
            {splitResult && (
              <div className="space-y-1.5">
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(splitResult.participants).map(([p, sp]) => (
                    <span key={p} className="data border border-line px-1.5 py-0.5 text-[11px]">
                      {p} → {sp}
                    </span>
                  ))}
                </div>
                <p className="text-[12px] text-ink-faint">
                  clips: {Object.entries(splitResult.clip_counts).map(([k, v]) => `${k} ${v}`).join(" · ")}
                </p>
                {splitResult.warnings.map((w) => (
                  <p key={w} className="text-[12px] text-warn">{w}</p>
                ))}
              </div>
            )}
            {!splitResult && !splitErr && (
              <Empty text="No splits generated yet. Deterministic per seed; each participant belongs to exactly one split." />
            )}
          </div>
        </Card>

        <Card title="Datasets">
          {datasets.loading && !datasets.data ? (
            <LoadError error={datasets.error} loading />
          ) : datasets.data && datasets.data.length > 0 ? (
            <ul className="divide-y divide-line/60">
              {datasets.data.map((d) => (
                <li key={d.dataset_id} className="flex items-center justify-between gap-3 py-2">
                  <div>
                    <p className="text-[13px] font-medium">{d.name}</p>
                    <p className="data text-[11px] text-ink-faint">{d.path}</p>
                  </div>
                  <StatusBadge tone="neutral">{d.clip_count} clips</StatusBadge>
                </li>
              ))}
            </ul>
          ) : (
            <Empty text="No datasets yet — the default one appears after your first record/import." />
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Distribution">
          {s && Object.keys(s.by_class).length > 0 ? (
            <div className="space-y-3">
              <div>
                <p className="label mb-1.5">By class</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(s.by_class).map(([k, v]) => (
                    <span key={k} className="data border border-line px-1.5 py-0.5 text-[11px]">{k}: {v}</span>
                  ))}
                </div>
              </div>
              <div>
                <p className="label mb-1.5">By modality</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(s.by_modality).map(([k, v]) => (
                    <span key={k} className="data border border-line px-1.5 py-0.5 text-[11px]">{k}: {v}</span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <Empty text="No labeled clips yet — distribution is empty, not zero-filled." />
          )}
        </Card>

        <Card title="Rules">
          <ul className="space-y-1.5 text-[13px] text-ink-soft">
            <li className="flex gap-2"><FileVideo size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden />Every clip is decoded and measured (frames, fps, duration, sha256) — never trusted blindly.</li>
            <li className="flex gap-2"><Split size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden />Splits are participant-based, never random row splits — no participant leaks across train/val/test.</li>
            <li className="flex gap-2"><Database size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden />Manifests live in data/manifests, splits in data/splits, raw clips in data/raw.</li>
            <li className="flex gap-2"><Camera size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden />Recording reads frames from the same bounded camera buffer Live Vision shows.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
