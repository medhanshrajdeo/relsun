// One shared loading affordance instead of several slightly different
// hand-rolled `animate-spin` divs and ad-hoc Loader2 icon usages.
export function Spinner({ size = 14, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{ width: size, height: size }}
      className={`inline-block shrink-0 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-500 dark:border-zinc-700 dark:border-t-zinc-400 ${className}`}
    />
  );
}
