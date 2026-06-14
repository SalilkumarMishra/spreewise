import { apiClient } from './client';

export interface GroupBalance {
  user_id: number;
  user: string;
  balance: string;
}

export interface SimplifiedPayment {
  payer_id: number;
  payer: string;
  receiver_id: number;
  receiver: string;
  amount: string;
}

export interface CalculationTraceStep {
  date: string;
  event_type: 'expense' | 'settlement';
  reference_id: string;
  delta: string;
  running_balance: string;
}

export interface UserExplanation {
  user_id: number;
  user: string;
  total_paid: string;
  total_owed: string;
  net_balance: string;
  expense_contributions: {
    expense_id: number;
    title: string;
    delta: string;
    breakdown: any;
  }[];
  settlement_contributions: {
    reference_id: string;
    amount: string;
    delta: string;
    breakdown: any;
  }[];
  calculation_trace: CalculationTraceStep[];
}

export interface LedgerEntry {
  user_id: number;
  delta: string;
}

export interface LedgerEvent {
  event_type: 'expense' | 'settlement';
  reference_id: string;
  event_date: string;
  entries: LedgerEntry[];
}

export async function getGroupBalances(groupId: number): Promise<GroupBalance[]> {
  const response = await apiClient.get(`/api/balances/groups/${groupId}/`);
  return response.data;
}

export async function getSimplifiedPayments(groupId: number): Promise<SimplifiedPayment[]> {
  const response = await apiClient.get(`/api/balances/groups/${groupId}/simplified/`);
  return response.data;
}

export async function getUserExplanation(groupId: number, userId: number): Promise<UserExplanation> {
  const response = await apiClient.get(`/api/balances/groups/${groupId}/users/${userId}/`);
  return response.data;
}

export async function getLedger(groupId: number): Promise<LedgerEvent[]> {
  const response = await apiClient.get(`/api/balances/groups/${groupId}/ledger/`);
  return response.data;
}
