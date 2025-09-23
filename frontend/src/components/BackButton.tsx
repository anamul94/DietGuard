import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const BackButton: React.FC = () => {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate(-1)}
      className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-6 transition-colors"
    >
      <ArrowLeft className="h-5 w-5" />
      <span>Back</span>
    </button>
  );
};

export default BackButton;