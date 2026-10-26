import { Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import Overview from "../pages/Overview";
import { Placeholder } from "../pages/Placeholder";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route
          path="vision"
          element={
            <Placeholder
              title="Live Vision"
              phase="Phase 3 — camera abstraction"
              note="Camera preview, providers and recognition readouts arrive with the camera runtime."
            />
          }
        />
        <Route
          path="lab"
          element={
            <Placeholder
              title="AI Lab"
              phase="Phase 5/6 — model registry"
              note="Model status, metadata and fusion thresholds appear once model artifacts exist."
            />
          }
        />
        <Route
          path="dataset"
          element={
            <Placeholder
              title="Dataset Studio"
              phase="Phase 4 — dataset tooling"
              note="Clip import, labelling, validation and splits arrive with the dataset backend."
            />
          }
        />
        <Route
          path="training"
          element={
            <Placeholder
              title="Training Center"
              phase="Phase 5/6 — training jobs"
              note="Real training jobs, logs and evaluation reports arrive with the training worker."
            />
          }
        />
        <Route
          path="history"
          element={
            <Placeholder
              title="Recognition History"
              phase="Phase 8 — local history"
              note="Persisted recognition events with filtering arrive with the history API."
            />
          }
        />
        <Route
          path="calibration"
          element={
            <Placeholder
              title="Calibration"
              phase="Phase 9 — calibration workflow"
              note="Guided camera framing and quality checks arrive with the vision pipeline."
            />
          }
        />
        <Route
          path="settings"
          element={
            <Placeholder
              title="Device Settings"
              phase="Phase 2/3 — settings API"
              note="Camera, thresholds, speech and retention controls arrive with their backend endpoints."
            />
          }
        />
        <Route
          path="health"
          element={
            <Placeholder
              title="System Health"
              phase="Phase 2 — diagnostics"
              note="Full diagnostics (WebSocket status, dependency checks, events) arrive with the diagnostics module."
            />
          }
        />
        <Route
          path="*"
          element={
            <Placeholder
              title="Not found"
              phase="404"
              note="This route does not exist."
            />
          }
        />
      </Route>
    </Routes>
  );
}
