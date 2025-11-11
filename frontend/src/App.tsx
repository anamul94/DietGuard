import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Footer from './components/Footer';
import HomePage from './pages/HomePage';
import UploadReportPage from './pages/UploadReportPage';
import UploadFoodPage from './pages/UploadFoodPage';
import DeleteDataPage from './pages/DeleteDataPage';
import MarkdownTestPage from './pages/MarkdownTestPage';
import HealthPage from './pages/HealthPage';
import TestLLMPage from './pages/TestLLMPage';

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-grow">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/upload-report" element={<UploadReportPage />} />
            <Route path="/upload-food" element={<UploadFoodPage />} />
            <Route path="/delete-data" element={<DeleteDataPage />} />
            <Route path="/markdown-test" element={<MarkdownTestPage />} />
            <Route path="/healthdb" element={<HealthPage />} />
            <Route path="/test-llm" element={<TestLLMPage />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;