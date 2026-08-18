const PHASES = [
  { n: 0, name: "Foundation", state: "in progress" },
  { n: 1, name: "Data foundation", state: "queued" },
  { n: 2, name: "Metric engine", state: "queued" },
  { n: 3, name: "API + vertical slice", state: "queued" },
  { n: 4, name: "Decomposition Studio", state: "queued" },
] as const;

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">RxGrowth IQ</h1>
      <p className="mt-2 text-[var(--color-muted)]">
        Prescription growth intelligence platform
      </p>

      <div className="mt-6 rounded-md border border-[var(--color-line)] px-4 py-3 text-sm">
        <strong>Synthetic data only.</strong> This platform contains no real
        prescription, patient, or licensed vendor data.
      </div>

      <h2 className="mt-10 text-sm font-medium uppercase tracking-wide text-[var(--color-muted)]">
        Build status
      </h2>
      <ul className="mt-3 divide-y divide-[var(--color-line)]">
        {PHASES.map((phase) => (
          <li key={phase.n} className="flex justify-between py-2 text-sm">
            <span>
              Phase {phase.n} &middot; {phase.name}
            </span>
            <span className="text-[var(--color-muted)]">{phase.state}</span>
          </li>
        ))}
      </ul>

      <p className="mt-10 text-xs text-[var(--color-muted)]">
        Dashboard arrives in Phase 3, once the metric engine it renders exists.
      </p>
    </main>
  );
}
