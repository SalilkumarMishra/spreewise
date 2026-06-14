import { apiClient } from './client';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  date_joined?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse extends AuthTokens {
  user?: UserInfo;
}

export interface RegisterResponse extends AuthTokens {
  user: UserInfo;
}

/**
 * POST /api/auth/login/
 * Authenticates with username + password and returns JWT tokens.
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await axios.post(`${API_BASE_URL}/api/auth/login/`, {
    username,
    password,
  });
  return response.data;
}

/**
 * POST /api/auth/register/
 * Registers a new user and returns JWT tokens + user profile.
 */
export async function register(
  fullName: string,
  username: string,
  email: string,
  password: string,
  confirmPassword: string
): Promise<RegisterResponse> {
  const response = await axios.post(`${API_BASE_URL}/api/auth/register/`, {
    full_name: fullName,
    username,
    email,
    password,
    confirm_password: confirmPassword,
  });
  return response.data;
}

/**
 * GET /api/auth/me/
 * Returns the currently authenticated user's profile.
 */
export async function getMe(): Promise<UserInfo> {
  const response = await apiClient.get('/api/auth/me/');
  return response.data;
}

/**
 * POST /api/auth/refresh/
 * Refreshes the access token using the stored refresh token.
 */
export async function refreshAccessToken(refreshToken: string): Promise<AuthTokens> {
  const response = await axios.post(`${API_BASE_URL}/api/auth/refresh/`, {
    refresh: refreshToken,
  });
  return response.data;
}

/**
 * POST /api/auth/logout/
 * Sends logout signal to backend (blacklists refresh token if enabled).
 */
export async function logout(refreshToken: string): Promise<void> {
  try {
    await apiClient.post('/api/auth/logout/', { refresh: refreshToken });
  } catch {
    // Swallow logout errors — always clear client state regardless
  }
}
