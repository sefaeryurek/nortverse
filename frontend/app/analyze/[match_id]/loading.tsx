export default function Loading() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800 px-5 py-4">
        <div className="h-5 w-56 animate-pulse rounded bg-slate-800" />
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-3" role="status" aria-live="polite">
        <div className="h-9 w-9 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <p className="text-sm text-slate-300">Analiz yükleniyor...</p>
      </div>
    </div>
  );
}
