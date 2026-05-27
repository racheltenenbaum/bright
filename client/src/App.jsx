import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import PropTypes from "prop-types";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";

const HomePage = lazy(() => import("./pages/HomePage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const PlanRoutePage = lazy(() => import("./pages/PlanRoutePage"));
const MyRoutesPage = lazy(() => import("./pages/MyRoutesPage"));
const MyAccountPage = lazy(() => import("./pages/MyAccountPage"));
const MySpotsPage = lazy(() => import("./pages/MySpotsPage"));
const SharedRoutePage = lazy(() => import("./pages/SharedRoutePage"));

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" />;
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
};

function sunAltitude(lat, lng) {
  const now = new Date();
  const jd = now / 86400000 + 2440587.5;
  const n = jd - 2451545.0;
  const L = (280.46 + 0.9856474 * n) % 360;
  const g = ((357.528 + 0.9856003 * n) % 360) * Math.PI / 180;
  const lam = (L + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * Math.PI / 180;
  const obliquity = 23.439 * Math.PI / 180;
  const dec = Math.asin(Math.sin(obliquity) * Math.sin(lam));
  const ra = Math.atan2(Math.cos(obliquity) * Math.sin(lam), Math.cos(lam)) * (12 / Math.PI);
  const gmst = ((18.697374558 + 24.06570982441908 * n) % 24 + 24) % 24;
  const lha = (((gmst + lng / 15 - ra) % 24) + 24) % 24;
  const ha = lha * 15 * Math.PI / 180;
  const latRad = lat * Math.PI / 180;
  return Math.asin(Math.sin(latRad) * Math.sin(dec) + Math.cos(latRad) * Math.cos(dec) * Math.cos(ha)) * 180 / Math.PI;
}

function Layout() {
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    function applyTheme(lat, lng) {
      document.body.classList.toggle("night-mode", sunAltitude(lat, lng) <= 0);
    }

    const lat = parseFloat(localStorage.getItem("bright_lat") || "51.505");
    const lng = parseFloat(localStorage.getItem("bright_lng") || "-0.09");
    applyTheme(lat, lng);

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        ({ coords }) => applyTheme(coords.latitude, coords.longitude),
        null,
        { timeout: 5000 },
      );
    }
  }, []);

  return (
    <>
      {isAuthenticated && <Navbar />}
      <div style={{ width: "100%", maxWidth: "700px", margin: "0 auto", flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/share/:token" element={<SharedRoutePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/plan"
              element={
                <ProtectedRoute>
                  <PlanRoutePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/my-routes"
              element={
                <ProtectedRoute>
                  <MyRoutesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/my-spots"
              element={
                <ProtectedRoute>
                  <MySpotsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/my-account"
              element={
                <ProtectedRoute>
                  <MyAccountPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </div>
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
