import { apiClient } from './client';

export interface GroupMembership {
  id: number;
  user_id: number;
  username: string;
  joined_at: string;
  left_at: string | null;
  is_active: boolean;
  role: string;
}

export interface Group {
  id: number;
  name: string;
  description: string;
  currency: string;
  is_archived: boolean;
  created_by: number;
  created_by_username: string;
  created_at: string;
  updated_at: string;
  members?: GroupMembership[];
  active_member_count?: number;
  total_member_count?: number;
}

export async function listGroups(includeArchived = false): Promise<Group[]> {
  const response = await apiClient.get(`/api/groups/?include_archived=${includeArchived}`);
  return response.data;
}

export async function getGroup(id: number): Promise<Group> {
  const response = await apiClient.get(`/api/groups/${id}/`);
  return response.data;
}

export async function createGroup(name: string, description: string, currency: string): Promise<Group> {
  const response = await apiClient.post('/api/groups/', {
    name,
    description,
    currency,
  });
  return response.data;
}

export async function archiveGroup(id: number): Promise<void> {
  await apiClient.delete(`/api/groups/${id}/`);
}

export async function addGroupMember(groupId: number, userId: number, joinedAt: string): Promise<GroupMembership> {
  const response = await apiClient.post(`/api/groups/${groupId}/members/`, {
    user_id: userId,
    joined_at: joinedAt,
  });
  return response.data;
}

export async function leaveGroup(groupId: number, membershipId: number, leftAt: string): Promise<GroupMembership> {
  const response = await apiClient.post(`/api/groups/${groupId}/members/${membershipId}/leave/`, {
    left_at: leftAt,
  });
  return response.data;
}
