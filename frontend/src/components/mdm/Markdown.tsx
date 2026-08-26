import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink } from "lucide-react";
import { useRecordModal } from "@/lib/recordModal";

// A search/request agent formats a record reference as [Name](record:ID)
// (see search_agent.py / party_request_agent.py's instructions) — this
// component is what turns that convention into a click that opens the
// record inline in the shared RecordPanelTray, instead of a normal
// anchor navigating away.
function ChatLink(props: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  const { open } = useRecordModal();
  const href = props.href ?? "";

  if (href.startsWith("record:")) {
    const id = Number(href.slice("record:".length));
    if (Number.isFinite(id)) {
      return (
        <button
          type="button"
          onClick={() => open(id)}
          className="inline-flex items-center gap-0.5 font-medium text-blue-600 underline decoration-blue-300 underline-offset-2 hover:text-blue-700 dark:text-blue-400 dark:decoration-blue-800 dark:hover:text-blue-300"
        >
          {props.children}
          <ExternalLink size={11} className="opacity-60" />
        </button>
      );
    }
  }

  return <a {...props} target="_blank" rel="noreferrer" className="underline" />;
}

// Shared by the Concierge chat and the Compare AI summary — both surface
// text drafted by an Anthropic agent, which comes back as GitHub-flavored
// markdown (bold, lists, tables, headings). Rendered properly rather than
// shown as raw asterisks/pipes/hashes.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // react-markdown's default urlTransform only allows a safe scheme
        // allowlist (http/https/mailto/tel/relative) and silently blanks
        // anything else — including our record:ID convention — so it has
        // to be explicitly let through here, same as the default handles
        // every other URL.
        urlTransform={(url) => (url.startsWith("record:") ? url : defaultUrlTransform(url))}
        components={{
          a: ChatLink,
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
