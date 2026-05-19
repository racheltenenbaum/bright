import { lazy, Suspense } from "react";
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

function Layout() {
  const { isAuthenticated } = useAuth();
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
