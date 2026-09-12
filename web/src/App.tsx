import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { Explore } from "./pages/Explore";
import { Build } from "./pages/Build";
import { Steps } from "./pages/Steps";
import { Query } from "./pages/Query";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="explore" element={<Explore />} />
        <Route path="build" element={<Build />} />
        <Route path="steps" element={<Steps />} />
        <Route path="query" element={<Query />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
