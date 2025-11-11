import React, { useState } from 'react';

const TestLLMPage: React.FC = () => {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const testLLM = async () => {
    setLoading(true);
    setResult(null);
    
    const apiUrl = `${process.env.REACT_APP_API_URL}/test_llm`;
    console.log('Testing API URL:', apiUrl);
    
    try {
      const response = await fetch(apiUrl);
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setResult(data);
    } catch (error: any) {
      console.error('API Error:', error);
      setResult({
        status: 'error',
        error: error.message,
        apiUrl: apiUrl
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">LLM Connection Test</h1>
      
      <button
        onClick={testLLM}
        disabled={loading}
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"
      >
        {loading ? 'Testing...' : 'Test LLM Connection'}
      </button>

      {result && (
        <div className="mt-6 p-4 border rounded-lg">
          {result.status === 'success' ? (
            <div className="text-green-600">
              <h3 className="text-xl font-bold">✅ LLM Connection Successful</h3>
              <p><strong>Query:</strong> {result.test_query}</p>
              <p><strong>Response:</strong> {result.llm_response}</p>
            </div>
          ) : (
            <div className="text-red-600">
              <h3 className="text-xl font-bold">❌ LLM Connection Failed</h3>
              <p><strong>Error:</strong> {result.error}</p>
              {result.apiUrl && <p><strong>API URL:</strong> {result.apiUrl}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestLLMPage;