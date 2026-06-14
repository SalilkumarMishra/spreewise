import { apiClient } from './client';

export interface ExpenseSplitData {
  user_id: number;
  username?: string;
  percentage_value?: string | null;
  shares_value?: string | null;
  exact_amount?: string | null;
  calculated_amount?: string;
}

export interface ExpenseSnapshot {
  id: number;
  version: number;
  payload_json: any;
  created_at: string;
}

export interface Expense {
  id: number;
  group: number;
  title: string;
  description: string;
  amount: string;
  currency: string;
  original_amount: string;
  original_currency: string;
  expense_category: string;
  source: string;
  expense_date: string;
  paid_by: number;
  paid_by_username?: string;
  split_type: 'equal' | 'percentage' | 'shares' | 'exact';
  status: 'active' | 'disputed' | 'import_review';
  notes: string;
  import_job: number | null;
  created_by: number;
  created_by_username?: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  splits?: ExpenseSplitData[];
  snapshots?: ExpenseSnapshot[];
}

export interface ExpenseInput {
  group_id: number;
  title: string;
  amount: number;
  currency: string;
  expense_date: string;
  paid_by_id: number;
  split_type: 'equal' | 'percentage' | 'shares' | 'exact';
  participant_ids: number[];
  splits?: {
    user_id: number;
    percentage_value?: number;
    shares_value?: number;
    exact_amount?: number;
  }[];
  description?: string;
  notes?: string;
  expense_category?: string;
  original_amount?: number;
  original_currency?: string;
  status?: 'active' | 'disputed' | 'import_review';
  source?: string;
}

export async function listExpenses(groupId: number, includeArchived = false): Promise<Expense[]> {
  const response = await apiClient.get(`/api/expenses/?group_id=${groupId}&include_archived=${includeArchived}`);
  return response.data;
}

export async function getExpense(id: number): Promise<Expense> {
  const response = await apiClient.get(`/api/expenses/${id}/`);
  return response.data;
}

export async function createExpense(input: ExpenseInput): Promise<Expense> {
  const response = await apiClient.post('/api/expenses/', input);
  return response.data;
}

export async function updateExpense(id: number, input: Partial<ExpenseInput>): Promise<Expense> {
  const response = await apiClient.put(`/api/expenses/${id}/`, input);
  return response.data;
}

export async function deleteExpense(id: number): Promise<void> {
  await apiClient.delete(`/api/expenses/${id}/`);
}
