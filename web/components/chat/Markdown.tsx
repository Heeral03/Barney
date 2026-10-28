import ReactMarkdown from "react-markdown";

/** Barney writes light markdown (bold, lists, italics). No raw HTML is ever rendered. */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        p: (p) => <p className="mb-3 leading-[1.75] last:mb-0" {...p} />,
        strong: (p) => <strong className="font-semibold text-ink" {...p} />,
        em: (p) => <em className="text-muted" {...p} />,
        ul: (p) => <ul className="mb-3 list-disc space-y-1.5 pl-5 marker:text-faint" {...p} />,
        ol: (p) => <ol className="mb-3 list-decimal space-y-1.5 pl-5 marker:text-faint" {...p} />,
        a: (p) => <a className="underline underline-offset-4" target="_blank" rel="noopener noreferrer" {...p} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
