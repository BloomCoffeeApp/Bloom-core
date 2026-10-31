import { DashboardPage } from './dashboard-page'

/** Mounted as the index route ("/", no splat), so no nested <Routes> here. */
export default function Module() {
  return <DashboardPage />
}
