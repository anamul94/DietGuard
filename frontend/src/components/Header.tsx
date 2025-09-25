import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, Brain, FileText } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header className="glass-effect shadow-lg sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="medical-gradient p-2 rounded-lg">
              <Brain className="h-8 w-8 text-white" />
            </div>
            <div>
              <Link to="/" className="text-2xl font-bold text-gray-800 hover:text-medical-700 transition-colors">
                DietGuard AI
              </Link>
              <p className="text-sm text-gray-600">AI-Powered Nutritionist</p>
            </div>
          </div>
          <div className="flex items-center space-x-6">
            <Link
              to="/markdown-test"
              className="flex items-center space-x-2 text-medical-600 hover:text-medical-800 transition-colors"
              title="View Markdown Rendering Test"
            >
              <FileText className="h-5 w-5" />
              <span className="text-sm font-medium">Test Markdown</span>
            </Link>
            <div className="flex items-center space-x-2">
              <Activity className="h-5 w-5 text-medical-600" />
              <span className="text-sm text-gray-600">Smart Health Analysis</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;