import axios from 'axios';
import { logger } from './logger';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://15.207.68.194:8010';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export interface UploadReportResponse {
  mobile_number: string;
  files_processed: number;
  individual_responses: Array<{
    filename: string;
    response: string;
  }>;
  combined_response: string;
}

export interface UploadFoodResponse {
  mobile_number: string;
  meal_time: string;
  files_processed: number;
  filenames: string[];
  food_analysis: string;
  nutritionist_recommendations: string;
}

export const uploadReport = async (
  mobileOrEmail: string,
  files: FileList
): Promise<UploadReportResponse> => {
  logger.info('Preparing report upload', { user: mobileOrEmail, fileCount: files.length });

  const formData = new FormData();
  formData.append('mobile_or_email', mobileOrEmail);

  for (let i = 0; i < files.length; i++) {
    logger.debug('Adding file to upload', { filename: files[i].name, size: files[i].size });
    formData.append('files', files[i]);
  }

  logger.info('Making API request', { endpoint: `${API_BASE_URL}/upload_report/` });

  try {
    const response = await api.post('/upload_report/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 60 second timeout
    });

    logger.info('Upload successful', { status: response.status, filesProcessed: response.data.files_processed });
    return response.data;
  } catch (error: any) {
    logger.error('Upload failed', { status: error.response?.status, data: error.response?.data, message: error.message });
    throw error;
  }
};

export const uploadFood = async (
  mobileOrEmail: string,
  mealTime: string,
  files: FileList
): Promise<UploadFoodResponse> => {
  logger.info('Preparing food upload', { user: mobileOrEmail, mealTime, fileCount: files.length });

  const formData = new FormData();
  formData.append('mobile_or_email', mobileOrEmail);
  formData.append('meal_time', mealTime);

  for (let i = 0; i < files.length; i++) {
    logger.debug('Adding file to upload', { filename: files[i].name, size: files[i].size });
    formData.append('files', files[i]);
  }

  logger.info('Making API request', { endpoint: `${API_BASE_URL}/upload_food/` });

  try {
    const response = await api.post('/upload_food/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 60 second timeout
    });

    logger.info('Food upload successful', { status: response.status, filesProcessed: response.data.files_processed });
    return response.data;
  } catch (error: any) {
    logger.error('Food upload failed', error, {
      user: mobileOrEmail,
      mealTime,
      fileCount: files.length,
      status: error.response?.status,
      data: error.response?.data
    });
    throw error;
  }
};

export const deleteReport = async (userId: string): Promise<{ message: string }> => {
  logger.info('Deleting report', { userId });

  try {
    const response = await api.delete(`/delete_report/${userId}`);
    logger.info('Report deleted successfully', { userId, status: response.status });
    return response.data;
  } catch (error: any) {
    logger.error('Delete report failed', error, { userId, status: error.response?.status });
    throw error;
  }
};

export const getReport = async (userId: string) => {
  logger.info('Fetching report', { userId });

  try {
    const response = await api.get(`/get_report/${userId}`);
    logger.info('Report fetched successfully', { userId, status: response.status });
    return response.data;
  } catch (error: any) {
    logger.error('Get report failed', error, { userId, status: error.response?.status });
    throw error;
  }
};

export const getNutrition = async (userId: string) => {
  logger.info('Fetching nutrition data', { userId });

  try {
    const response = await api.get(`/get_nutrition/${userId}`);
    logger.info('Nutrition data fetched successfully', { userId, status: response.status });
    return response.data;
  } catch (error: any) {
    logger.error('Get nutrition failed', error, { userId, status: error.response?.status });
    throw error;
  }
};