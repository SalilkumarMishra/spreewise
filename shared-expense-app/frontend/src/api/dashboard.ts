import { apiClient } from './client';

export interface DashboardData {
  my_groups: {
    id: number;
    name: string;
    currency: string;
    role: string;
    is_archived: boolean;
  }[];
  group_count: number;
  net_balance: {
    you_owe: number;
    you_are_owed: number;
    net: number;
  };
  recent_expenses: {
    id: number;
    title: string;
    amount: string;
    currency: string;
    paid_by: string;
    group: string;
    expense_date: string;
  }[];
  recent_settlements: {
    id: number;
    amount: string;
    currency: string;
    payer: string;
    receiver: string;
    group: string;
    payment_date: string;
  }[];
  pending_import_reviews: number;
}

export async function getDashboard(): Promise<DashboardData> {
  const response = await apiClient.get('/api/auth/dashboard/');
  return response.data;
}
