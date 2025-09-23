import React from 'react';
import { Shield, Clock, Trash2 } from 'lucide-react';

const Footer: React.FC = () => {
  return (
    <footer className="glass-effect mt-16 border-t">
      <div className="container mx-auto px-4 py-8">
        <div className="grid md:grid-cols-3 gap-6 text-center">
          <div className="flex flex-col items-center space-y-2">
            <Shield className="h-8 w-8 text-medical-600" />
            <h3 className="font-semibold text-gray-800">Privacy First</h3>
            <p className="text-sm text-gray-600">Your data is never permanently stored</p>
          </div>
          <div className="flex flex-col items-center space-y-2">
            <Clock className="h-8 w-8 text-nutrition-600" />
            <h3 className="font-semibold text-gray-800">24-Hour Storage</h3>
            <p className="text-sm text-gray-600">Data automatically deleted after 24 hours</p>
          </div>
          <div className="flex flex-col items-center space-y-2">
            <Trash2 className="h-8 w-8 text-red-500" />
            <h3 className="font-semibold text-gray-800">Manual Deletion</h3>
            <p className="text-sm text-gray-600">Delete your data anytime</p>
          </div>
        </div>
        <div className="mt-8 pt-6 border-t text-center">
          <p className="text-gray-600">&copy; 2024 DietGuard AI. AI-Powered Nutritional Analysis.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;