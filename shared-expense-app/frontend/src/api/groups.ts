import { apiClient } from './client';

export interface GroupMembership {
  id: number;
  user_id: number;
  username: string;
  full_name: string;
  email: string;
  joined_at: string;
  left_at: string | null;
  is_active: boolean;
  role: string;
  joined_via_invite: boolean;
  invite_code_used: string | null;
}

export interface Group {
  id: number;
  name: string;
  description: string;
  currency: string;
  is_archived: boolean;
  invite_code: string;
  created_by: number;
  created_by_username: string;
  current_user_role: string | null;
  created_at: string;
  updated_at: string;
  members?: GroupMembership[];
  active_member_count?: number;
  total_member_count?: number;
}

export interface UserSearchResult {
  id: number;
  username: string;
  email: string;
  full_name: string;
  first_name: string;
  last_name: string;
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

export async function removeGroupMember(groupId: number, membershipId: number): Promise<void> {
  await apiClient.delete(`/api/groups/${groupId}/members/${membershipId}/remove/`);
}

export async function updateMemberRole(
  groupId: number,
  membershipId: number,
  role: 'admin' | 'member'
): Promise<GroupMembership> {
  const response = await apiClient.post(`/api/groups/${groupId}/members/${membershipId}/role/`, { role });
  return response.data;
}

export async function joinGroupByInviteCode(inviteCode: string): Promise<{
  detail: string;
  group_id: number;
  membership: GroupMembership;
}> {
  const response = await apiClient.post('/api/groups/join/', { invite_code: inviteCode });
  return response.data;
}

export async function searchUsers(query: string): Promise<UserSearchResult[]> {
  if (query.trim().length < 2) return [];
  const response = await apiClient.get(`/api/users/search/?q=${encodeURIComponent(query)}`);
  return response.data;
}

