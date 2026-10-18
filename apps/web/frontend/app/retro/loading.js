// Keeps the retro shell's dark surface while its pages load, instead of
// inheriting the default shell's cream skeleton from app/loading.js.
export default function RetroLoading() {
  return (
    <main className="retroPage" aria-busy="true">
      <p className="retroMuted" role="status">
        Loading…
      </p>
    </main>
  );
}
