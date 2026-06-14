import { apiClient } from './client';

export interface SettlementSnapshot {
  id: number;
  version: number;
  payload_json: any;
  created_at: string;
}

export interface Settlement {
  id: number;
  reference_id: string;
  group: number;
  payer: number;
  payer_username?: string;
  receiver: number;
  receiver_username?: string;
  amount: string;
  currency: string;
  original_amount: string;
  original_currency: string;
  payment_date: string;
  notes: string;
  settlement_category: 'direct_payment' | 'bank_transfer' | 'cash' | 'upi' | 'imported';
  source: string;
  status: 'active' | 'disputed' | 'import_review';
  import_job: number | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  snapshots?: SettlementSnapshot[];
}

export interface SettlementInput {
  group_id: number;
  payer_id: number;
  receiver_id: number;
  amount: number;
  currency: string;
  payment_date: string;
  notes?: string;
  settlement_category?: 'direct_payment' | 'bank_transfer' | 'cash' | 'upi' | 'imported';
  source?: string;
  status?: 'active' | 'disputed' | 'import_review';
  original_amount?: number;
  original_currency?: string;
}

export async function listSettlements(groupId: number, includeArchived = false): Promise<Settlement[]> {
  const response = await apiClient.get(`/api/settlements/?group_id=${groupId}&include_archived=${includeArchived}`);
  return response.data;
}

export async function getSettlement(id: number): Promise<Settlement> {
  const response = await apiClient.get(`/api/settlements/${id}/`);
  return response.data;
}

export async function createSettlement(input: SettlementInput): Promise<Settlement> {
  const response = await apiClient.post('/api/settlements/', input);
  return response.data;
}

export async function updateSettlement(id: number, input: Partial<SettlementInput>): Promise<Settlement> {
  const response = await apiClient.put(`/api/settlements/${id}/`, input);
  return response.data;
}

export async function deleteSettlement(id: number): Promise<void> {
  await apiClient.delete(`/api/settlements/${id}/`);
}
