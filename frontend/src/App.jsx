import { Navigate, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout.jsx';
import { Overview } from './pages/Overview.jsx';
import { Transactions } from './pages/Transactions.jsx';
import { Analytics } from './pages/Analytics.jsx';
import { AnalyticsCategories } from './pages/AnalyticsCategories.jsx';
import { AnalyticsTags } from './pages/AnalyticsTags.jsx';
import { Categories } from './pages/Categories.jsx';
import { Tags } from './pages/Tags.jsx';
import { ImportExport } from './pages/ImportExport.jsx';
import { Sql } from './pages/Sql.jsx';
import { NotFound } from './pages/NotFound.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="transaktionen" element={<Transactions />} />
        {/* The tab itself has no content of its own — it is the sub-tabs plus
            the date range they share, so it opens on the first one. */}
        <Route path="auswertungen" element={<Analytics />}>
          <Route index element={<Navigate to="kategorien" replace />} />
          <Route path="kategorien" element={<AnalyticsCategories />} />
          <Route path="tags" element={<AnalyticsTags />} />
        </Route>
        <Route path="kategorien" element={<Categories />} />
        <Route path="tags" element={<Tags />} />
        <Route path="import-export" element={<ImportExport />} />
        <Route path="sql" element={<Sql />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
