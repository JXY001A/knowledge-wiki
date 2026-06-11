export function LoadingSpinner({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted">
      <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
      <p className="mt-3 text-sm">{text}</p>
    </div>
  );
}
