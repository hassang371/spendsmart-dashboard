export default function InsightsLoading() {
  return (
    <div
      className="mx-auto flex w-full max-w-5xl flex-col gap-4"
      aria-busy="true"
      aria-live="polite"
    >
      <div className="h-8 w-1/3 animate-pulse rounded bg-muted" />
      <div className="h-64 w-full animate-pulse rounded-xl bg-muted" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-40 animate-pulse rounded-xl bg-muted" />
        <div className="h-40 animate-pulse rounded-xl bg-muted" />
      </div>
      <div className="h-32 w-full animate-pulse rounded-xl bg-muted" />
    </div>
  );
}
