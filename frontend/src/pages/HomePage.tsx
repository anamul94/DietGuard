import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Camera, Trash2, Brain, Stethoscope, Apple } from 'lucide-react';

const HomePage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <div className="medical-gradient p-4 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center">
          <Brain className="h-10 w-10 text-white" />
        </div>
        <h1 className="text-4xl font-bold text-gray-800 mb-4">
          AI-Powered Nutritionist
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Upload your medical reports and food images to get personalized nutritional guidance 
          from our AI doctors specialized in clinical nutrition.
        </p>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
        <Link to="/upload-report" className="glass-effect rounded-xl p-6 hover:shadow-lg transition-all duration-300 group">
          <div className="flex items-center space-x-4 mb-4">
            <div className="bg-medical-100 p-3 rounded-lg group-hover:bg-medical-200 transition-colors">
              <FileText className="h-6 w-6 text-medical-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-800">Upload Medical Reports</h3>
          </div>
          <p className="text-gray-600">
            Upload your lab results, medical reports, or health documents for AI analysis by Dr. Maria Chen.
          </p>
        </Link>

        <Link to="/upload-food" className="glass-effect rounded-xl p-6 hover:shadow-lg transition-all duration-300 group">
          <div className="flex items-center space-x-4 mb-4">
            <div className="bg-nutrition-100 p-3 rounded-lg group-hover:bg-nutrition-200 transition-colors">
              <Camera className="h-6 w-6 text-nutrition-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-800">Analyze Food</h3>
          </div>
          <p className="text-gray-600">
            Take photos of your meals for nutritional analysis and personalized recommendations.
          </p>
        </Link>

        <Link to="/delete-data" className="glass-effect rounded-xl p-6 hover:shadow-lg transition-all duration-300 group">
          <div className="flex items-center space-x-4 mb-4">
            <div className="bg-red-100 p-3 rounded-lg group-hover:bg-red-200 transition-colors">
              <Trash2 className="h-6 w-6 text-red-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-800">Delete Data</h3>
          </div>
          <p className="text-gray-600">
            Remove your stored data anytime. All data is automatically deleted after 24 hours.
          </p>
        </Link>
      </div>

      {/* AI Doctors Section */}
      <div className="glass-effect rounded-xl p-8 mb-12">
        <h2 className="text-2xl font-bold text-center text-gray-800 mb-8">Meet Your AI Medical Team</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="bg-medical-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
              <Stethoscope className="h-8 w-8 text-medical-600" />
            </div>
            <h3 className="font-semibold text-gray-800 mb-2">Dr. Maria Chen</h3>
            <p className="text-sm text-gray-600">Diagnostic Medicine Specialist</p>
            <p className="text-xs text-gray-500 mt-1">Medical Report Analysis</p>
          </div>
          <div className="text-center">
            <div className="bg-nutrition-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
              <Apple className="h-8 w-8 text-nutrition-600" />
            </div>
            <h3 className="font-semibold text-gray-800 mb-2">Dr. James Rodriguez</h3>
            <p className="text-sm text-gray-600">Certified Nutritionist</p>
            <p className="text-xs text-gray-500 mt-1">Food Analysis Expert</p>
          </div>
          <div className="text-center">
            <div className="bg-purple-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
              <Brain className="h-8 w-8 text-purple-600" />
            </div>
            <h3 className="font-semibold text-gray-800 mb-2">Dr. Sarah Mitchell</h3>
            <p className="text-sm text-gray-600">Clinical Nutritionist</p>
            <p className="text-xs text-gray-500 mt-1">15 Years Experience</p>
          </div>
        </div>
      </div>

      {/* Privacy Notice */}
      <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-xl p-6 border border-blue-200">
        <div className="flex items-start space-x-3">
          <div className="bg-blue-100 p-2 rounded-lg">
            <Brain className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-800 mb-2">Privacy & Data Security</h3>
            <p className="text-sm text-gray-600">
              Your health data is processed securely and automatically deleted after 24 hours. 
              We don't store personal information permanently. All AI analysis is performed with 
              medical-grade privacy standards.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;