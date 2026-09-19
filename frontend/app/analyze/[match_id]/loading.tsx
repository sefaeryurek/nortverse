export default function AnalyzeLoading() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800 px-5 py-4">
        <div className="h-5 w-64 max-w-full animate-pulse rounded bg-slate-800" />
      </div>
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="mb-5 h-10 w-10 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <p className="text-sm font-medium text-slate-200">Analiz yükleniyor...</p>
        <p className="mt-1 text-xs text-slate-400">İlk analiz veri kaynağına göre daha uzun sürebilir.</p>
      </div>
    </div>
  );
}
