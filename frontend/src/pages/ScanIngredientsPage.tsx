import React, { useState, useEffect } from 'react';
import { Camera, Upload, Loader, CheckCircle, AlertCircle, AlertTriangle, Shield, ShieldAlert, ShieldCheck, X, Smartphone, Search } from 'lucide-react';
import QRCode from 'react-qr-code';
import { scanIngredients, ScanIngredientsResponse, IngredientDetail } from '../utils/api';
import BackButton from '../components/BackButton';

const getRatingColor = (rating: string) => {
  switch (rating.toLowerCase()) {
    case 'green': return { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300', icon: '🟢', label: 'Safe' };
    case 'yellow': return { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300', icon: '🟡', label: 'Caution' };
    case 'red': return { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300', icon: '🔴', label: 'Avoid' };
    default: return { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300', icon: '⚪', label: 'Unknown' };
  }
};

const getNutrigradeColor = (grade: string) => {
  switch (grade.toUpperCase()) {
    case 'A': return 'bg-green-500';
    case 'B': return 'bg-lime-500';
    case 'C': return 'bg-yellow-500';
    case 'D': return 'bg-red-500';
    default: return 'bg-gray-500';
  }
};

const IngredientCard: React.FC<{ ingredient: IngredientDetail; index: number }> = ({ ingredient, index }) => {
  const [expanded, setExpanded] = useState(false);
  const rating = getRatingColor(ingredient.health_rating);

  return (
    <div className={`rounded-xl border-2 ${rating.border} overflow-hidden transition-all duration-300 hover:shadow-md`}>
      <div
        className={`${rating.bg} px-5 py-4 cursor-pointer flex items-center justify-between`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-3">
          <span className="text-xl">{rating.icon}</span>
          <div>
            <h4 className="font-semibold text-gray-800">{ingredient.name}</h4>
            {ingredient.common_name && ingredient.common_name !== ingredient.name && (
              <p className="text-sm text-gray-600">Also known as: {ingredient.common_name}</p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <span className={`text-xs font-bold px-3 py-1 rounded-full ${rating.bg} ${rating.text} border ${rating.border}`}>
            {rating.label}
          </span>
          <span className="text-gray-400 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      <div className="px-5 py-4 bg-white">
        <p className="text-gray-700 mb-2">{ingredient.short_explanation}</p>

        {expanded && (
          <div className="mt-4 space-y-4 animate-fadeIn">
            <div className="bg-gray-50 rounded-lg p-4">
              <h5 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wide">Detailed Explanation</h5>
              <p className="text-gray-700 leading-relaxed">{ingredient.detailed_explanation}</p>
            </div>

            {ingredient.concerns.length > 0 && (
              <div className="bg-orange-50 rounded-lg p-4">
                <h5 className="text-sm font-semibold text-orange-700 mb-2 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" /> Concerns
                </h5>
                <ul className="space-y-1">
                  {ingredient.concerns.map((concern, i) => (
                    <li key={i} className="text-sm text-orange-700 flex items-start gap-2">
                      <span className="mt-1">•</span> {concern}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {ingredient.age_restrictions && (
              <div className="bg-purple-50 rounded-lg p-3">
                <p className="text-sm text-purple-700 flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" /> <strong>Age Restriction:</strong> {ingredient.age_restrictions}
                </p>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {Object.entries(ingredient.dietary_flags).map(([key, value]) => (
                <span
                  key={key}
                  className={`text-xs px-3 py-1 rounded-full font-medium ${value
                      ? 'bg-green-100 text-green-700 border border-green-200'
                      : 'bg-red-100 text-red-600 border border-red-200'
                    }`}
                >
                  {value ? '✓' : '✗'} {key.charAt(0).toUpperCase() + key.slice(1)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const ScanIngredientsPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScanIngredientsResponse | null>(null);
  const [error, setError] = useState('');
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const domain = process.env.REACT_APP_DOMAIN || 'localhost:3000';
  const currentUrl = `http://${domain}/scan-ingredients`;

  const handleFileChange = (selectedFile: File) => {
    setFile(selectedFile);
    setResult(null);
    setError('');
    const reader = new FileReader();
    reader.onloadend = () => setPreview(reader.result as string);
    reader.readAsDataURL(selectedFile);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a food packaging image');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await scanIngredients(file);
      setResult(response);
    } catch (err: any) {
      console.error('Scan error:', err);
      setError(err.response?.data?.detail || err.message || 'Scan failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const analysis = result?.ingredient_analysis;
  const overallRating = analysis ? getRatingColor(analysis.overall_rating) : null;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <BackButton />

        {/* Header */}
        <div className="text-center mb-8">
          <div className="bg-amber-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <Search className="h-8 w-8 text-amber-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Ingredient Scanner</h1>
          <p className="text-gray-600">Upload food packaging to analyze ingredients with AI-powered health ratings by Dr. Sarah Chen</p>
        </div>

        {/* QR Code - Desktop only */}
        {!isMobile && (
          <div className="glass-effect rounded-xl p-6 mb-8">
            <div className="flex items-center space-x-2 mb-4">
              <Smartphone className="h-5 w-5 text-amber-600" />
              <h3 className="text-lg font-semibold text-gray-800">Mobile Scan</h3>
            </div>
            <div className="text-center">
              <div className="bg-white p-4 rounded-lg inline-block shadow-sm">
                <QRCode value={currentUrl} size={200} />
              </div>
              <p className="text-sm text-gray-600 mt-2">Scan with your mobile to take a photo of the packaging</p>
            </div>
          </div>
        )}

        {/* Upload Form */}
        <div className="glass-effect rounded-xl p-6 mb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {/* Camera Capture */}
              <div className="border-2 border-solid border-amber-500 rounded-lg p-4 text-center bg-amber-50">
                <Camera className="h-10 w-10 text-amber-600 mx-auto mb-2" />
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
                  className="hidden"
                  id="ingredient-camera"
                />
                <label htmlFor="ingredient-camera" className="cursor-pointer">
                  <span className="text-amber-600 font-semibold">📸 Take Photo of Packaging</span>
                </label>
                <p className="text-xs text-amber-600 mt-1">Point camera at ingredient list</p>
              </div>

              {/* Gallery Upload */}
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-amber-400 transition-colors">
                <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
                  className="hidden"
                  id="ingredient-gallery"
                />
                <label htmlFor="ingredient-gallery" className="cursor-pointer">
                  <span className="text-gray-600 font-medium">📁 Choose from Gallery</span>
                </label>
                <p className="text-xs text-gray-500 mt-1">Select an image of food packaging</p>
              </div>
            </div>

            {/* Preview */}
            {file && preview && (
              <div className="relative bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2 text-sm text-gray-700">
                    <Camera className="h-4 w-4" />
                    <span>{file.name}</span>
                    <span className="text-gray-400">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setFile(null); setPreview(''); setResult(null); }}
                    className="text-red-500 hover:text-red-700 p-1"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded-lg shadow-sm" />
              </div>
            )}

            {error && (
              <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !file}
              className="w-full bg-gradient-to-r from-amber-500 to-orange-500 text-white py-3 px-6 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader className="h-5 w-5 animate-spin" />
                  <span>Analyzing Ingredients...</span>
                </>
              ) : (
                <>
                  <Search className="h-5 w-5" />
                  <span>Scan Ingredients</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Results */}
        {analysis && (
          <div className="space-y-6 animate-fadeIn">
            {/* Overall Summary Card */}
            <div className="glass-effect rounded-xl p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                  <h2 className="text-xl font-semibold text-gray-800">Analysis Complete</h2>
                </div>
                <div className="flex items-center space-x-3">
                  {/* NutriGrade Badge */}
                  <div className="text-center">
                    <p className="text-xs text-gray-500 font-medium mb-1">NutriGrade</p>
                    <div className={`${getNutrigradeColor(analysis.nutrigrade)} text-white font-bold text-2xl w-12 h-12 rounded-xl flex items-center justify-center shadow-lg`}>
                      {analysis.nutrigrade}
                    </div>
                  </div>
                  {/* Overall Rating */}
                  <div className="text-center">
                    <p className="text-xs text-gray-500 font-medium mb-1">Overall</p>
                    <div className={`${overallRating?.bg} ${overallRating?.text} font-bold text-sm px-4 py-3 rounded-xl border ${overallRating?.border}`}>
                      {overallRating?.icon} {overallRating?.label}
                    </div>
                  </div>
                </div>
              </div>

              {/* Summary */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <p className="text-blue-800 leading-relaxed">{analysis.summary}</p>
              </div>

              {/* Critical Warnings */}
              {analysis.critical_warnings.length > 0 && (
                <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
                  <h3 className="font-semibold text-red-800 mb-3 flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5" /> Critical Warnings
                  </h3>
                  <ul className="space-y-2">
                    {analysis.critical_warnings.map((warning, i) => (
                      <li key={i} className="text-red-700 flex items-start gap-2 text-sm">
                        <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Ingredients Grid */}
            <div className="glass-effect rounded-xl p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                  <Shield className="h-5 w-5 text-amber-600" />
                  Ingredients ({analysis.ingredients.length})
                </h3>
                <div className="flex gap-3 text-xs">
                  <span className="flex items-center gap-1">🟢 Safe</span>
                  <span className="flex items-center gap-1">🟡 Caution</span>
                  <span className="flex items-center gap-1">🔴 Avoid</span>
                </div>
              </div>
              <div className="space-y-3">
                {analysis.ingredients.map((ingredient, index) => (
                  <IngredientCard key={index} ingredient={ingredient} index={index} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScanIngredientsPage;
