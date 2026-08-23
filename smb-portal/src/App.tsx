import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { BillingUsage } from "./pages/BillingUsage";
import { Onboarding } from "./pages/Onboarding";
import { QAChat } from "./pages/QAChat";
import { WalkthroughPaywall } from "./pages/WalkthroughPaywall";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/onboarding" replace />} />
        <Route path="onboarding" element={<Onboarding />} />
        <Route path="chat" element={<QAChat />} />
        <Route path="walkthrough" element={<WalkthroughPaywall />} />
        <Route path="billing" element={<BillingUsage />} />
      </Route>
    </Routes>
  );
}
