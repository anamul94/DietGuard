import React, { useState, useEffect } from 'react';
import { Camera, Upload, Loader, CheckCircle, AlertCircle, QrCode, Smartphone } from 'lucide-react';
import QRCode from 'react-qr-code';
import { uploadFood } from '../utils/api';
import MarkdownRenderer from '../components/MarkdownRenderer';

const UploadFoodPage: React.FC = () => {
  const [mobileOrEmail, setMobileOrEmail] = useState('');
  const [mealTime, setMealTime] = useState('');
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const currentUrl = window.location.href;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files || files.length === 0) {
      setError('Please select food images to upload');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await uploadFood(mobileOrEmail, mealTime, files);
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="bg-nutrition-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <Camera className="h-8 w-8 text-nutrition-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Food Analysis</h1>
          <p className="text-gray-600">Upload food images for nutritional analysis by Dr. James Rodriguez & Dr. Sarah Mitchell</p>
        </div>

        {/* QR Code Section - Only show on desktop */}
        {!isMobile && (
          <div className="glass-effect rounded-xl p-6 mb-8">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Smartphone className="h-5 w-5 text-nutrition-600" />
                <h3 className="text-lg font-semibold text-gray-800">Mobile Upload</h3>
              </div>
              <button
                onClick={() => setShowQR(!showQR)}
                className="flex items-center space-x-2 text-nutrition-600 hover:text-nutrition-700"
              >
                <QrCode className="h-5 w-5" />
                <span>{showQR ? 'Hide QR' : 'Show QR'}</span>
              </button>
            </div>
            
            {showQR && (
              <div className="text-center">
                <div className="bg-white p-4 rounded-lg inline-block shadow-sm">
                  <QRCode value={currentUrl} size={200} />
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  Scan with your mobile device to upload food images directly
                </p>
              </div>
            )}
          </div>
        )}

        {/* Upload Form */}
        <div className="glass-effect rounded-xl p-6 mb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mobile Number or Email
              </label>
              <input
                type="text"
                value={mobileOrEmail}
                onChange={(e) => setMobileOrEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-nutrition-500 focus:border-transparent"
                placeholder="Enter your mobile number or email"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Meal Time
              </label>
              <select
                value={mealTime}
                onChange={(e) => setMealTime(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-nutrition-500 focus:border-transparent"
                required
              >
                <option value="">Select meal time</option>
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Food Images
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-nutrition-400 transition-colors">
                <Camera className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <input
                  type="file"
                  multiple
                  accept=".jpg,.jpeg,.png"
                  onChange={(e) => setFiles(e.target.files)}
                  className="hidden"
                  id="food-upload"
                />
                <label htmlFor="food-upload" className="cursor-pointer">
                  <span className="text-nutrition-600 font-medium">Click to upload</span>
                  <span className="text-gray-500"> or drag and drop</span>
                </label>
                <p className="text-sm text-gray-500 mt-2">JPG, PNG up to 10MB each</p>
              </div>
              {files && (
                <div className="mt-2">
                  <p className="text-sm text-gray-600">
                    {files.length} image(s) selected
                  </p>
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
                <AlertCircle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-nutrition-500 to-nutrition-600 text-white py-3 px-6 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader className="h-5 w-5 animate-spin" />
                  <span>Analyzing Food...</span>
                </>
              ) : (
                <>
                  <Upload className="h-5 w-5" />
                  <span>Analyze Food</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Results */}
        {result && (
          <div className="glass-effect rounded-xl p-6">
            <div className="flex items-center space-x-2 mb-6">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <h2 className="text-xl font-semibold text-gray-800">Analysis Complete</h2>
            </div>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
              <p className="text-green-800">
                <strong>Meal:</strong> {result.meal_time} | 
                <strong> Images:</strong> {result.files_processed} | 
                <strong> Patient:</strong> {result.mobile_number}
              </p>
            </div>

            <div className="space-y-8">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-4">🍎 Dr. James Rodriguez - Food Analysis:</h3>
                <MarkdownRenderer content={result.food_analysis} />
              </div>
              
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-4">🏥 Dr. Sarah Mitchell - Nutritional Recommendations:</h3>
                <MarkdownRenderer content={result.nutritionist_recommendations} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadFoodPage;