import React, { useState } from 'react';
import { FileText, Upload, Loader, CheckCircle, AlertCircle } from 'lucide-react';
import { uploadReport } from '../utils/api';
import MarkdownRenderer from '../components/MarkdownRenderer';

const UploadReportPage: React.FC = () => {
  const [mobileOrEmail, setMobileOrEmail] = useState('');
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files || files.length === 0) {
      setError('Please select files to upload');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    
    try {
      console.log('Uploading files:', files.length, 'for user:', mobileOrEmail);
      const response = await uploadReport(mobileOrEmail, files);
      console.log('Upload response:', response);
      setResult(response);
    } catch (err: any) {
      console.error('Upload error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Upload failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="bg-medical-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <FileText className="h-8 w-8 text-medical-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Medical Report Analysis</h1>
          <p className="text-gray-600">Upload your medical reports for AI analysis by Dr. Maria Chen</p>
        </div>

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
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-medical-500 focus:border-transparent"
                placeholder="Enter your mobile number or email"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Medical Reports (PDF or Images)
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-medical-400 transition-colors">
                <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => setFiles(e.target.files)}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <span className="text-medical-600 font-medium">Click to upload multiple files</span>
                  <span className="text-gray-500"> or drag and drop</span>
                </label>
                <p className="text-sm text-gray-500 mt-2">PDF, JPG, PNG up to 10MB each • Multiple files supported</p>
              </div>
              {files && (
                <div className="mt-3 bg-blue-50 rounded-lg p-3">
                  <p className="text-sm font-medium text-blue-800 mb-2">
                    {files.length} file(s) selected for analysis:
                  </p>
                  <div className="space-y-1">
                    {Array.from(files).map((file, index) => (
                      <div key={index} className="flex items-center space-x-2 text-sm text-blue-700">
                        <FileText className="h-4 w-4" />
                        <span>{file.name}</span>
                        <span className="text-blue-500">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center space-x-2 text-red-600 mb-2">
                  <AlertCircle className="h-5 w-5" />
                  <span className="font-semibold">Upload Error</span>
                </div>
                <p className="text-red-700 text-sm">{error}</p>
                <p className="text-red-600 text-xs mt-2">
                  Check browser console for detailed error information.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full medical-gradient text-white py-3 px-6 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader className="h-5 w-5 animate-spin" />
                  <span>Analyzing Reports...</span>
                </>
              ) : (
                <>
                  <Upload className="h-5 w-5" />
                  <span>Upload & Analyze</span>
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
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-800 font-medium">
                    ✅ Analysis Complete for {result.files_processed} file(s)
                  </p>
                  <p className="text-green-700 text-sm">
                    Patient ID: {result.mobile_number}
                  </p>
                </div>
                <div className="text-green-600">
                  <CheckCircle className="h-8 w-8" />
                </div>
              </div>
            </div>

            <div className="space-y-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-6">📋 Individual File Analysis by Dr. Maria Chen:</h3>
              
              {result.individual_responses.map((response: any, index: number) => (
                <div key={index} className="border border-gray-200 rounded-lg p-6 bg-white shadow-sm">
                  <div className="flex items-center space-x-2 mb-4">
                    <FileText className="h-5 w-5 text-medical-600" />
                    <h4 className="text-lg font-medium text-gray-800">{response.filename}</h4>
                  </div>
                  <MarkdownRenderer content={response.response} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadReportPage;