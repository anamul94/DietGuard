import React, { useState, useEffect } from 'react';
import { Trash2, AlertTriangle, CheckCircle, Loader, User, Database, MessageSquare, FileText, CheckSquare, Square, Eye, X } from 'lucide-react';
import BackButton from '../components/BackButton';
import { deleteReport, deleteNutrition, deleteAllData, getReport, getNutrition } from '../utils/api';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

const SettingsPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Selection state
  const [selectedItems, setSelectedItems] = useState({
    report: false,
    food: false,
    chat: false
  });

  // Modal / Viewer state
  const [viewerContent, setViewerContent] = useState<{ title: string; content: string } | null>(null);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8010';

  useEffect(() => {
    const storedEmail = localStorage.getItem('dietguard_user_email');
    if (storedEmail) {
      setEmail(storedEmail);
    }
  }, []);

  const toggleSelection = (key: keyof typeof selectedItems) => {
    setSelectedItems(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const hasSelection = Object.values(selectedItems).some(Boolean);

  const handleViewData = async (type: 'Report' | 'Nutrition') => {
    if (!email) {
      setMessage({ type: 'error', text: 'Please enter your email to view data.' });
      return;
    }

    setLoading(prev => ({ ...prev, [`view${type}`]: true }));
    setMessage(null);

    try {
      if (type === 'Report') {
        const data = await getReport(email);
        setViewerContent({
          title: 'Medical Report Analysis',
          content: data.data?.combined_response || 'No analysis content found.'
        });
      } else {
        const data = await getNutrition(email);
        // Nutrition data can be complex, format it for display
        const content = `
### Meal Time: ${data.meal_time || 'N/A'}
#### Food Analysis:
${data.food_analysis || 'No analysis available.'}

#### Nutritionist Recommendations:
${data.nutritionist_recommendations || 'No recommendations available.'}
        `;
        setViewerContent({
          title: 'Nutrition & Food Analysis',
          content: content
        });
      }
    } catch (err: any) {
      console.error(`Error fetching ${type}:`, err);
      setMessage({
        type: 'error',
        text: err.response?.status === 404 ? `No ${type} data found for this email.` : `Failed to fetch ${type} data.`
      });
    } finally {
      setLoading(prev => ({ ...prev, [`view${type}`]: false }));
    }
  };

  const handleDeleteSelected = async () => {
    if (!email) {
      setMessage({ type: 'error', text: 'Please enter your email to manage data.' });
      return;
    }

    if (!window.confirm('Are you sure you want to delete the selected data? This action cannot be undone.')) {
      return;
    }

    setLoading(prev => ({ ...prev, selected: true }));
    setMessage(null);

    const results: string[] = [];

    try {
      if (selectedItems.report) {
        await deleteReport(email);
        results.push('Medical Reports');
      }
      if (selectedItems.food) {
        await deleteNutrition(email);
        results.push('Food Data');
      }
      if (selectedItems.chat) {
        await axios.delete(`${API_URL}/api/chat/history/${email}`);
        results.push('Chat History');
      }

      setMessage({
        type: 'success',
        text: `Deleted: ${results.join(', ')}`
      });

      setSelectedItems({
        report: false,
        food: false,
        chat: false
      });
    } catch (err: any) {
      console.error('Error deleting data:', err);
      setMessage({
        type: 'error',
        text: 'Failed to delete some items. Please try again.'
      });
    } finally {
      setLoading(prev => ({ ...prev, selected: false }));
    }
  };

  const handleDeleteAll = async () => {
    if (!email) {
      setMessage({ type: 'error', text: 'Please enter your email to manage data.' });
      return;
    }

    if (!window.confirm('Are you sure you want to PERMANENTLY delete ALL your data? This action cannot be undone.')) {
      return;
    }

    setLoading(prev => ({ ...prev, all: true }));
    setMessage(null);

    try {
      await deleteAllData(email);
      setMessage({ type: 'success', text: 'All data deleted successfully.' });
    } catch (err: any) {
      console.error('Error deleting all data:', err);
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to delete all data.'
      });
    } finally {
      setLoading(prev => ({ ...prev, all: false }));
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <BackButton />

        <div className="text-center mb-8">
          <div className="bg-gray-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <User className="h-8 w-8 text-gray-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Data Settings</h1>
          <p className="text-gray-600">Manage your stored data and privacy</p>
        </div>

        {/* Identity Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Your Email ID
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Enter your email"
          />
        </div>

        {message && (
          <div className={`rounded-lg p-4 mb-8 flex items-center gap-3 ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
            {message.type === 'success' ? <CheckCircle className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
            <span>{message.text}</span>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-8">
          <div className="p-6 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
            <h2 className="font-semibold text-gray-900">Stored Data</h2>
            {hasSelection && (
              <button
                onClick={handleDeleteSelected}
                disabled={loading.selected}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 text-sm font-medium disabled:opacity-50"
              >
                {loading.selected ? <Loader className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Delete Selected
              </button>
            )}
          </div>

          <div className="divide-y divide-gray-200">
            {/* Medical Reports */}
            <div className="p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors group">
              <div
                className={`flex-shrink-0 cursor-pointer ${selectedItems.report ? 'text-blue-600' : 'text-gray-400'}`}
                onClick={() => toggleSelection('report')}
              >
                {selectedItems.report ? <CheckSquare className="h-6 w-6" /> : <Square className="h-6 w-6" />}
              </div>
              <div className="p-3 bg-blue-100 rounded-lg text-blue-600">
                <FileText className="h-6 w-6" />
              </div>
              <div className="flex-grow">
                <h3 className="font-semibold text-gray-900">Medical Reports</h3>
                <p className="text-sm text-gray-500">Uploaded PDF/Image reports and AI analysis</p>
              </div>
              <button
                onClick={() => handleViewData('Report')}
                disabled={loading.viewReport}
                className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                title="View Data"
              >
                {loading.viewReport ? <Loader className="h-5 w-5 animate-spin" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            {/* Food Data */}
            <div className="p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors group">
              <div
                className={`flex-shrink-0 cursor-pointer ${selectedItems.food ? 'text-blue-600' : 'text-gray-400'}`}
                onClick={() => toggleSelection('food')}
              >
                {selectedItems.food ? <CheckSquare className="h-6 w-6" /> : <Square className="h-6 w-6" />}
              </div>
              <div className="p-3 bg-green-100 rounded-lg text-green-600">
                <Database className="h-6 w-6" />
              </div>
              <div className="flex-grow">
                <h3 className="font-semibold text-gray-900">Food & Nutrition Data</h3>
                <p className="text-sm text-gray-500">Logged meals and nutritional analysis</p>
              </div>
              <button
                onClick={() => handleViewData('Nutrition')}
                disabled={loading.viewNutrition}
                className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                title="View Data"
              >
                {loading.viewNutrition ? <Loader className="h-5 w-5 animate-spin" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            {/* Chat History */}
            <div className="p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors group">
              <div
                className={`flex-shrink-0 cursor-pointer ${selectedItems.chat ? 'text-blue-600' : 'text-gray-400'}`}
                onClick={() => toggleSelection('chat')}
              >
                {selectedItems.chat ? <CheckSquare className="h-6 w-6" /> : <Square className="h-6 w-6" />}
              </div>
              <div className="p-3 bg-purple-100 rounded-lg text-purple-600">
                <MessageSquare className="h-6 w-6" />
              </div>
              <div className="flex-grow">
                <h3 className="font-semibold text-gray-900">Chat History</h3>
                <p className="text-sm text-gray-500">Conversation logs with the medical chatbot</p>
              </div>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div>
          <h3 className="text-red-600 font-bold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Danger Zone
          </h3>
          <div className="bg-red-50 rounded-xl border border-red-200 p-6 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-red-900">Delete All Data</h3>
              <p className="text-sm text-red-700">Permanently remove all your data from our system</p>
            </div>
            <button
              onClick={handleDeleteAll}
              disabled={loading.all}
              className="px-6 py-2 bg-red-600 text-white hover:bg-red-700 rounded-lg transition-colors flex items-center gap-2 font-medium shadow-sm disabled:opacity-50"
            >
              {loading.all ? <Loader className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Delete Everything
            </button>
          </div>
        </div>
      </div>

      {/* Viewer Modal */}
      {viewerContent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col overflow-hidden">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50">
              <h3 className="text-xl font-bold text-gray-900">{viewerContent.title}</h3>
              <button
                onClick={() => setViewerContent(null)}
                className="p-2 hover:bg-gray-200 rounded-full transition-colors"
              >
                <X className="h-6 w-6 text-gray-500" />
              </button>
            </div>
            <div className="p-8 overflow-y-auto prose max-w-none">
              <ReactMarkdown>{viewerContent.content}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
