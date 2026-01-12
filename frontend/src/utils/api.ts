import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8010';

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
  console.log('API: Preparing upload for', mobileOrEmail, 'with', files.length, 'files');

  const formData = new FormData();
  formData.append('mobile_or_email', mobileOrEmail);

  for (let i = 0; i < files.length; i++) {
    console.log('API: Adding file', files[i].name, 'size:', files[i].size);
    formData.append('files', files[i]);
  }

  console.log('API: Making request to', `${API_BASE_URL}/upload_report/`);

  try {
    const response = await api.post('/upload_report/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 60 second timeout
    });

    console.log('API: Success response:', response.status, response.data);
    return response.data;
  } catch (error: any) {
    console.error('API: Upload failed:', error.response?.status, error.response?.data, error.message);
    throw error;
  }
};

export const uploadFood = async (
  mobileOrEmail: string,
  mealTime: string,
  files: FileList
): Promise<UploadFoodResponse> => {
  const formData = new FormData();
  formData.append('mobile_or_email', mobileOrEmail);
  formData.append('meal_time', mealTime);

  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }

  const response = await api.post('/upload_food/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const deleteReport = async (userId: string): Promise<{ message: string }> => {
  const response = await api.delete(`/delete_report/${userId}`);
  return response.data;
};

export const getReport = async (userId: string) => {
  const response = await api.get(`/get_report/${userId}`);
  return response.data;
};

export const getNutrition = async (userId: string) => {
  const response = await api.get(`/get_nutrition/${userId}`);
  return response.data;
};

export const deleteNutrition = async (userId: string): Promise<{ message: string }> => {
  const response = await api.delete(`/delete_nutrition/${userId}`);
  return response.data;
};

export const deleteAllData = async (userId: string): Promise<{ message: string; details: any }> => {
  const response = await api.delete(`/delete_all_data/${userId}`);
  return response.data;
};