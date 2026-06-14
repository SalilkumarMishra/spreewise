import axios from 'axios';

// Backend is hosted on http://127.0.0.1:8000
const API_BASE_URL = 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Axios request interceptor to append Basic Auth token dynamically
apiClient.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('spreewise_token');
    if (token && config.headers) {
      config.headers['Authorization'] = `Basic ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Axios response interceptor to handle 401s and redirect to login if needed
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      sessionStorage.removeItem('spreewise_token');
      sessionStorage.removeItem('spreewise_user');
      // If we are not on the login page, trigger a reload to push the router to login
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
