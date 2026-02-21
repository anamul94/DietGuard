import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Footer from './components/Footer';
import FloatingChatbot from './components/FloatingChatbot';
import HomePage from './pages/HomePage';
import UploadReportPage from './pages/UploadReportPage';
import UploadFoodPage from './pages/UploadFoodPage';
import ScanIngredientsPage from './pages/ScanIngredientsPage';
import DeleteDataPage from './pages/DeleteDataPage';
import MarkdownTestPage from './pages/MarkdownTestPage';
import SettingsPage from './pages/SettingsPage';

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
            <Route path="/scan-ingredients" element={<ScanIngredientsPage />} />
            <Route path="/delete-data" element={<DeleteDataPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/markdown-test" element={<MarkdownTestPage />} />
          </Routes>
        </main>
        <Footer />
        <FloatingChatbot />
      </div>
    </Router>
  );
}

export default App;