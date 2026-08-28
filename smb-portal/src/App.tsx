import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { AdminGuard, CustomerGuard, GuestOnly } from "./auth/RouteGuards";
import { Layout } from "./components/Layout";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminLogin } from "./pages/AdminLogin";
import { BillingUsage } from "./pages/BillingUsage";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Onboarding } from "./pages/Onboarding";
import { QAChat } from "./pages/QAChat";
import { Register } from "./pages/Register";
import { WalkthroughPaywall } from "./pages/WalkthroughPaywall";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route
            index
            element={
              <GuestOnly>
                <Landing />
              </GuestOnly>
            }
          />
          <Route
            path="login"
            element={
              <GuestOnly>
                <Login />
              </GuestOnly>
            }
          />
          <Route
            path="register"
            element={
              <GuestOnly>
                <Register />
              </GuestOnly>
            }
          />
          <Route path="onboarding" element={<Onboarding />} />
          <Route element={<CustomerGuard />}>
            <Route path="chat" element={<QAChat />} />
            <Route path="walkthrough" element={<WalkthroughPaywall />} />
            <Route path="billing" element={<BillingUsage />} />
          </Route>
        </Route>

        <Route path="admin/login" element={<AdminLogin />} />
        <Route element={<AdminGuard />}>
          <Route path="admin" element={<AdminDashboard />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
