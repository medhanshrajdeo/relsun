import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Shared by the Concierge chat and the Compare AI summary — both surface
// text drafted by an Anthropic agent, which comes back as GitHub-flavored
// markdown (bold, lists, tables, headings). Rendered properly rather than
// shown as raw asterisks/pipes/hashes.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: (props) => <a {...props} target="_blank" rel="noreferrer" className="underline" />,
          table: (props) => (
            <div className="my-2 overflow-x-auto">
              <table {...props} className="w-full min-w-max border-collapse text-xs" />
            </div>
          ),
          th: (props) => (
            <th
              {...props}
              className="border-b border-zinc-300 px-2 py-1 text-left font-medium dark:border-zinc-700"
            />
          ),
          td: (props) => <td {...props} className="border-b border-zinc-200 px-2 py-1 dark:border-zinc-800" />,
          ul: (props) => <ul {...props} className="my-1.5 list-disc space-y-0.5 pl-5" />,
          ol: (props) => <ol {...props} className="my-1.5 list-decimal space-y-0.5 pl-5" />,
          p: (props) => <p {...props} className="mb-2 last:mb-0" />,
          h1: (props) => <p {...props} className="mb-2 text-sm font-semibold last:mb-0" />,
          h2: (props) => <p {...props} className="mb-2 text-sm font-semibold last:mb-0" />,
          h3: (props) => <p {...props} className="mb-2 text-sm font-semibold last:mb-0" />,
          code: (props) => (
            <code
              {...props}
              className="rounded bg-zinc-200/70 px-1 py-0.5 font-mono text-[0.85em] dark:bg-zinc-800"
            />
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
