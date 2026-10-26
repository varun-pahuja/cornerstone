import { Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import Overview from "../pages/Overview";
import LiveVision from "../pages/LiveVision";
import AiLab from "../pages/AiLab";
import DatasetStudio from "../pages/DatasetStudio";
import TrainingCenter from "../pages/TrainingCenter";
import History from "../pages/History";
import Calibration from "../pages/Calibration";
import DeviceSettings from "../pages/DeviceSettings";
import SystemHealth from "../pages/SystemHealth";

function NotFound() {
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold tracking-tight">Not found</h1>
      <p className="text-[13px] text-ink-faint">This route does not exist.</p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="vision" element={<LiveVision />} />
        <Route path="lab" element={<AiLab />} />
        <Route path="dataset" element={<DatasetStudio />} />
        <Route path="training" element={<TrainingCenter />} />
        <Route path="history" element={<History />} />
        <Route path="calibration" element={<Calibration />} />
        <Route path="settings" element={<DeviceSettings />} />
        <Route path="health" element={<SystemHealth />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
