import ReactMarkdown from 'react-markdown'

// Kept out of the shared ui index so react-markdown only loads with lesson pages.
export const Markdown = ({ children }: { children: string }) => (
  <div className="md">
    <ReactMarkdown>{children}</ReactMarkdown>
  </div>
)
