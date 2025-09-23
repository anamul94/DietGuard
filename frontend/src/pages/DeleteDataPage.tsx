import React, { useState } from 'react';
import { Trash2, AlertTriangle, CheckCircle, Loader } from 'lucide-react';
import { deleteReport } from '../utils/api';
import BackButton from '../components/BackButton';

const DeleteDataPage: React.FC = () => {
  const [userId, setUserId] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) {
      setError('Please enter your mobile number or email');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess(false);
    
    try {
      await deleteReport(userId);
      setSuccess(true);
      setUserId('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Deletion failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <BackButton />
        {/* Header */}
        <div className="text-center mb-8">
          <div className="bg-red-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <Trash2 className="h-8 w-8 text-red-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Delete Your Data</h1>
          <p className="text-gray-600">Remove your stored medical and nutritional data</p>
        </div>

        {/* Warning Notice */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="h-6 w-6 text-yellow-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-yellow-800 mb-2">Important Information</h3>
              <ul className="text-sm text-yellow-700 space-y-1">
                <li>• All your medical reports and food analysis data will be permanently deleted</li>
                <li>• This action cannot be undone</li>
                <li>• Data is automatically deleted after 24 hours anyway</li>
                <li>• No personal information is stored permanently on our servers</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Delete Form */}
        <div className="glass-effect rounded-xl p-6 mb-8">
          <form onSubmit={handleDelete} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mobile Number or Email
              </label>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                placeholder="Enter the mobile number or email used for uploads"
                required
              />
              <p className="text-sm text-gray-500 mt-1">
                This should match the identifier you used when uploading data
              </p>
            </div>

            {error && (
              <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
                <AlertTriangle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-3 rounded-lg">
                <CheckCircle className="h-5 w-5" />
                <span>Your data has been successfully deleted</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-red-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader className="h-5 w-5 animate-spin" />
                  <span>Deleting Data...</span>
                </>
              ) : (
                <>
                  <Trash2 className="h-5 w-5" />
                  <span>Delete My Data</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Privacy Information */}
        <div className="glass-effect rounded-xl p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Privacy & Data Handling</h3>
          <div className="space-y-3 text-sm text-gray-600">
            <p>
              <strong>Automatic Deletion:</strong> All uploaded data (medical reports, food images, and analysis results) 
              is automatically deleted from our servers after 24 hours.
            </p>
            <p>
              <strong>No Permanent Storage:</strong> We don't store any personal information, medical data, 
              or food images permanently. Everything is processed and then removed.
            </p>
            <p>
              <strong>Secure Processing:</strong> All AI analysis is performed with medical-grade security 
              and privacy standards. Your data never leaves our secure processing environment.
            </p>
            <p>
              <strong>Manual Deletion:</strong> You can delete your data anytime before the 24-hour 
              automatic deletion using this form.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeleteDataPage;