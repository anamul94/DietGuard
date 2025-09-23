import React from 'react';
import ReactMarkdown from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        components={{
          table: ({ children }) => (
            <div className="overflow-x-auto mb-6">
              <table className="w-full border-collapse border border-gray-300 rounded-lg overflow-hidden shadow-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-medical-100">{children}</thead>
          ),
          tbody: ({ children }) => (
            <tbody>{children}</tbody>
          ),
          th: ({ children }) => (
            <th className="bg-medical-100 text-medical-700 font-semibold p-3 border border-gray-300 text-left whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="p-3 border border-gray-300 bg-white align-top">
              {children}
            </td>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-gray-50">{children}</tr>
          ),
          h1: ({ children }) => (
            <h1 className="text-3xl font-bold text-medical-700 mb-6 flex items-center gap-3">
              🏥 {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-semibold text-nutrition-700 mb-4 mt-6 flex items-center gap-2">
              {children}
            </h2>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-yellow-400 bg-yellow-50 p-4 my-4 rounded-r-lg shadow-sm">
              <div className="flex items-start gap-2">
                <span className="text-yellow-600 font-bold">⚠️</span>
                <div>{children}</div>
              </div>
            </blockquote>
          ),
          strong: ({ children }) => (
            <strong className="text-red-600 font-bold">{children}</strong>
          ),
          code: ({ children }) => (
            <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono text-gray-800">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;