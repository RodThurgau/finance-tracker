import { Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout.jsx';
import { Overview } from './pages/Overview.jsx';
import { Transactions } from './pages/Transactions.jsx';
import { Categories } from './pages/Categories.jsx';
import { Tags } from './pages/Tags.jsx';
import { ImportExport } from './pages/ImportExport.jsx';
import { NotFound } from './pages/NotFound.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="transaktionen" element={<Transactions />} />
        <Route path="kategorien" element={<Categories />} />
        <Route path="tags" element={<Tags />} />
        <Route path="import-export" element={<ImportExport />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
