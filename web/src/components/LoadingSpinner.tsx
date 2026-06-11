export function LoadingSpinner({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <div className="w-6 h-6 border-2 border-gray-200 border-t-accent rounded-full animate-spin" />
      <p className="mt-3 text-sm">{text}</p>
    </div>
  );
}
