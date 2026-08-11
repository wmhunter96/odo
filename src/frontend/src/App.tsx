import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import BottomNav from "./components/BottomNav";
import Dashboard from "./pages/Dashboard";
import NewFillUp from "./pages/NewFillUp";
import History from "./pages/History";
import FillUpDetail from "./pages/FillUpDetail";
import Settings from "./pages/Settings";
import { ThemeProvider } from "./context/ThemeContext";

// Charts pulls in recharts (~150kB gzipped) -- code-split it out of the
// main bundle since most visits are just logging a fill-up.
const Charts = lazy(() => import("./pages/Charts"));

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <header className="app-header">
          <h1>⛽ Odo</h1>
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/new-fillup" element={<NewFillUp />} />
            <Route path="/history" element={<History />} />
            <Route path="/fillup/:id" element={<FillUpDetail />} />
            <Route
              path="/charts"
              element={
                <Suspense fallback={<div className="spinner" />}>
                  <Charts />
                </Suspense>
              }
            />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
        <BottomNav />
      </BrowserRouter>
    </ThemeProvider>
  );
}
