import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { logger } from '../utils/logger';

const HealthPage: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        logger.info('Fetching health status from backend');
        const response = await axios.get(`${process.env.REACT_APP_API_URL}/health`);
        logger.info('Health status received', response.data);
        setHealthStatus(response.data);
      } catch (err: any) {
        const error = err as Error;
        logger.error('Failed to fetch health status', error);
        setError('Failed to fetch health status');
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
  }, []);

  if (loading) return <div className="container mx-auto px-4 py-8">Loading...</div>;
  if (error) return <div className="container mx-auto px-4 py-8 text-red-600">{error}</div>;

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Health Status</h1>
      <div className="bg-white rounded-lg shadow p-6">
        <pre className="text-sm">{JSON.stringify(healthStatus, null, 2)}</pre>
      </div>
    </div>
  );
};

export default HealthPage;