import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Table components - simplified to work with CSS
          table: ({ children }) => (
            <div className="table-wrapper">
              <table className="nutrition-table">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          th: ({ children }) => <th>{children}</th>,
          td: ({ children }) => <td>{children}</td>,
          tr: ({ children }) => <tr>{children}</tr>,
          
          // Headers with medical/nutrition icons
          h1: ({ children }) => (
            <h1 className="medical-header">
              🏥 {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="nutrition-header">
              🥗 {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="section-header">
              📊 {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="subsection-header">
              {children}
            </h4>
          ),
          
          // Lists with proper spacing and styling
          ul: ({ children }) => (
            <ul className="nutrition-list">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="nutrition-list ordered">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="nutrition-list-item">
              {children}
            </li>
          ),
          
          // Blockquotes for warnings/notes
          blockquote: ({ children }) => (
            <blockquote className="medical-alert">
              <div className="alert-content">
                <span className="alert-icon">⚠️</span>
                <div className="alert-text">{children}</div>
              </div>
            </blockquote>
          ),
          
          // Inline elements
          strong: ({ children }) => (
            <strong className="highlight-text">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="emphasis-text">
              {children}
            </em>
          ),
          
          // Code blocks
          code: ({ children }) => (
            <code className="inline-code">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="code-block">
              {children}
            </pre>
          ),
          
          // Links
          a: ({ children, href }) => (
            <a href={href} className="medical-link" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          
          // Paragraphs with proper spacing
          p: ({ children }) => (
            <p className="nutrition-paragraph">
              {children}
            </p>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;