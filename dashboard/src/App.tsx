import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { AsrTrendsPage } from "./pages/AsrTrendsPage";
import { AttackFeedPage } from "./pages/AttackFeedPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { PolicyEditorPage } from "./pages/PolicyEditorPage";
import { ToolMatrixPage } from "./pages/ToolMatrixPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<AttackFeedPage />} />
        <Route path="asr" element={<AsrTrendsPage />} />
        <Route path="policy" element={<PolicyEditorPage />} />
        <Route path="tools" element={<ToolMatrixPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="audit" element={<AuditLogPage />} />
      </Route>
    </Routes>
  );
}
