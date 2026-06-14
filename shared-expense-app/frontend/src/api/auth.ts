import { apiClient } from './client';

export interface UserInfo {
  id: number;
  username: string;
}

/**
 * Validates credentials by making a test request to the groups list.
 * If successful, we scan the returned groups to discover the user's integer ID.
 */
export async function login(username: string, password: string): Promise<UserInfo> {
  const token = btoa(`${username}:${password}`);
  
  // Make a request with the temporary auth header
  const response = await apiClient.get('/api/groups/', {
    headers: {
      'Authorization': `Basic ${token}`,
    },
  });

  if (response.status !== 200) {
    throw new Error('Authentication failed');
  }

  // Scanning returned groups to discover our user ID
  let userId = 0;
  const groups = response.data;
  
  for (const group of groups) {
    if (group.created_by_username === username) {
      userId = group.created_by;
      break;
    }
  }

  // If not found in created_by, we can try to fetch detail of a group to see members list,
  // but if we don't find it, we can resolve as 0 and update it later during group creations/lookups.
  
  return {
    id: userId,
    username,
  };
}
