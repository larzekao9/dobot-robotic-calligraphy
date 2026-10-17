import { AdminPage } from "./pages/AdminPage";
import { ConverterPage } from "./pages/ConverterPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JobsPage } from "./pages/JobsPage";
import { PreviewPage } from "./pages/PreviewPage";
import { RobotPage } from "./pages/RobotPage";
import { useRoute } from "./lib/router";

export function App() {
  const { path, params } = useRoute();
  switch (path) {
    case "/preview":
      return <PreviewPage params={params} />;
    case "/jobs":
      return <JobsPage params={params} />;
    case "/history":
      return <HistoryPage />;
    case "/admin":
      return <AdminPage />;
    case "/robot":
      return <RobotPage />;
    default:
      return <ConverterPage />;
  }
}
