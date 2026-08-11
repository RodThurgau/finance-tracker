import { CategoryManager } from '../components/CategoryManager.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { RulesSection } from '../components/RulesSection.jsx';

export function Categories() {
  return (
    <>
      <PageHeader
        title="Kategorien"
        description="Kategorien, Unterkategorien und Regeln verwalten."
      />

      <section className="mb-10">
        <CategoryManager />
      </section>

      <section>
        <RulesSection />
      </section>
    </>
  );
}
