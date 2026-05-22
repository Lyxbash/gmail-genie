import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Activity from "./pages/Activity";
import ReviewQueue from "./pages/ReviewQueue";
import Metrics from "./pages/Metrics";
import Settings from "./pages/Settings";
import { DeveloperModeProvider } from "./hooks/useDeveloperMode";

export default function App() {
  return (
    <DeveloperModeProvider>
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
    </DeveloperModeProvider>
  );
}
