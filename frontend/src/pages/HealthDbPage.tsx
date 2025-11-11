import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { logger } from '../utils/logger';

const HealthDbPage: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkFullHealth = async () => {
      try {
        logger.info('Checking full stack health (frontend -> backend -> database)');
        const response = await axios.get(`${process.env.REACT_APP_API_URL}/health`);
        logger.info('Full stack health check completed', response.data);
        setHealthStatus(response.data);
      } catch (err) {
        logger.error('Full stack health check failed', err);
        setError('Failed to fetch health status');
      } finally {
        setLoading(false);
      }
    };

    checkFullHealth();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-600 bg-green-50';
      case 'degraded': return 'text-yellow-600 bg-yellow-50';
      case 'unhealthy': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  if (loading) return <div className="container mx-auto px-4 py-8">Loading health status...</div>;
  if (error) return <div className="container mx-auto px-4 py-8 text-red-600">{error}</div>;

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">System Health Status</h1>
      
      <div className="grid gap-6">
        {/* Overall Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Overall System Status</h2>
          <div className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(healthStatus?.status)}`}>
            {healthStatus?.status?.toUpperCase()}
          </div>
          <div className="mt-4 text-sm text-gray-600">
            <p>Service: {healthStatus?.service}</p>
            <p>Version: {healthStatus?.version}</p>
          </div>
        </div>

        {/* Component Health Checks */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Component Health</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 border rounded">
              <span className="font-medium">Frontend</span>
              <div className="inline-flex px-3 py-1 rounded-full text-sm font-medium text-green-600 bg-green-50">
                HEALTHY
              </div>
            </div>
            <div className="flex items-center justify-between p-3 border rounded">
              <span className="font-medium">Backend API</span>
              <div className="inline-flex px-3 py-1 rounded-full text-sm font-medium text-green-600 bg-green-50">
                HEALTHY
              </div>
            </div>
            <div className="flex items-center justify-between p-3 border rounded">
              <span className="font-medium">Database</span>
              <div className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(healthStatus?.checks?.database)}`}>
                {healthStatus?.checks?.database?.toUpperCase()}
              </div>
            </div>
          </div>
        </div>

        {/* Raw Response */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Raw Health Response</h2>
          <pre className="text-sm bg-gray-50 p-4 rounded overflow-auto">
            {JSON.stringify(healthStatus, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default HealthDbPage;