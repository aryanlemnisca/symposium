import ReactMarkdown from 'react-markdown';

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose prose-invert prose-sm max-w-none" style={{ color: 'var(--color-text)' }}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold mt-6 mb-3" style={{ color: 'var(--color-teal)' }}>{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-bold mt-5 mb-2" style={{ color: 'var(--color-text)' }}>{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-bold mt-4 mb-2" style={{ color: 'var(--color-text)' }}>{children}</h3>,
          p: ({ children }) => <p className="mb-3 leading-relaxed text-sm">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 pl-4 list-disc text-sm">{children}</ul>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          strong: ({ children }) => <strong style={{ color: 'var(--color-teal)' }}>{children}</strong>,
          hr: () => <hr className="my-4" style={{ borderColor: 'var(--color-border)' }} />,
          blockquote: ({ children }) => (<blockquote className="pl-4 my-3 text-sm" style={{ borderLeft: '3px solid var(--color-teal)', color: 'var(--color-text-dim)' }}>{children}</blockquote>),
        }}
      >{content}</ReactMarkdown>
    </div>
  );
}
