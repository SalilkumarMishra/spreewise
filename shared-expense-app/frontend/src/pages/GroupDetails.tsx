import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getGroup, addGroupMember, leaveGroup } from '../api/groups';
import type { GroupMembership } from '../api/groups';
import { listExpenses, createExpense, updateExpense, deleteExpense, getExpense } from '../api/expenses';
import type { Expense, ExpenseInput } from '../api/expenses';
import { listSettlements, createSettlement, deleteSettlement } from '../api/settlements';
import { getGroupBalances, getSimplifiedPayments, getUserExplanation } from '../api/balances';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Dialog } from '../components/ui/Dialog';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { ArrowRightLeft, Plus, Trash2, UserPlus, AlertCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

export const GroupDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const groupId = Number(id);
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  
  const [activeTab, setActiveTab] = useState<'expenses' | 'settlements' | 'balances' | 'trace' | 'members'>('expenses');
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null);
  
  const [isSettlementModalOpen, setIsSettlementModalOpen] = useState(false);
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [leavingMember, setLeavingMember] = useState<GroupMembership | null>(null);
  const [leaveDate, setLeaveDate] = useState('');
  
  const [selectedTraceUser, setSelectedTraceUser] = useState<number | null>(null);
  const [selectedSnapshotExpense, setSelectedSnapshotExpense] = useState<Expense | null>(null);

  // Queries
  const { data: group, isLoading: groupLoading } = useQuery({
    queryKey: ['group', groupId],
    queryFn: () => getGroup(groupId),
  });

  const { data: expenses, isLoading: expensesLoading } = useQuery({
    queryKey: ['expenses', groupId],
    queryFn: () => listExpenses(groupId),
  });

  const { data: settlements, isLoading: settlementsLoading } = useQuery({
    queryKey: ['settlements', groupId],
    queryFn: () => listSettlements(groupId),
  });

  const { data: balances } = useQuery({
    queryKey: ['balances', groupId],
    queryFn: () => getGroupBalances(groupId),
  });

  const { data: simplified } = useQuery({
    queryKey: ['simplified', groupId],
    queryFn: () => getSimplifiedPayments(groupId),
  });

  const { data: traceData } = useQuery({
    queryKey: ['trace', groupId, selectedTraceUser],
    queryFn: () => getUserExplanation(groupId, selectedTraceUser!),
    enabled: !!selectedTraceUser,
  });

  // Auto select active trace user
  useEffect(() => {
    if (group?.members && group.members.length > 0 && !selectedTraceUser) {
      setSelectedTraceUser(group.members[0].user_id);
    }
  }, [group, selectedTraceUser]);

  // Mutations
  const expenseMutation = useMutation({
    mutationFn: (input: ExpenseInput) => 
      editingExpense 
        ? updateExpense(editingExpense.id, input)
        : createExpense(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses', groupId] });
      queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      queryClient.invalidateQueries({ queryKey: ['simplified', groupId] });
      queryClient.invalidateQueries({ queryKey: ['trace'] });
      setIsExpenseModalOpen(false);
      setEditingExpense(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Error saving expense. Verify members dates.');
    }
  });

  const deleteExpenseMutation = useMutation({
    mutationFn: (expId: number) => deleteExpense(expId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses', groupId] });
      queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      queryClient.invalidateQueries({ queryKey: ['simplified', groupId] });
      queryClient.invalidateQueries({ queryKey: ['trace'] });
    }
  });

  const settlementMutation = useMutation({
    mutationFn: (input: any) => createSettlement(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settlements', groupId] });
      queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      queryClient.invalidateQueries({ queryKey: ['simplified', groupId] });
      queryClient.invalidateQueries({ queryKey: ['trace'] });
      setIsSettlementModalOpen(false);
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Error saving settlement.');
    }
  });

  const deleteSettlementMutation = useMutation({
    mutationFn: (settleId: number) => deleteSettlement(settleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settlements', groupId] });
      queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      queryClient.invalidateQueries({ queryKey: ['simplified', groupId] });
      queryClient.invalidateQueries({ queryKey: ['trace'] });
    }
  });

  const memberMutation = useMutation({
    mutationFn: (input: { userId: number, joinedAt: string }) => 
      addGroupMember(groupId, input.userId, input.joinedAt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['group', groupId] });
      setIsMemberModalOpen(false);
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Error adding member.');
    }
  });

  const leaveMutation = useMutation({
    mutationFn: (input: { membershipId: number, leftAt: string }) => 
      leaveGroup(groupId, input.membershipId, input.leftAt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['group', groupId] });
      setLeavingMember(null);
      setLeaveDate('');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Error logging leave date.');
    }
  });

  // Expense Form Setup
  const expenseFormSchema = z.object({
    title: z.string().min(1, 'Title is required'),
    amount: z.coerce.number().positive('Amount must be positive'),
    currency: z.string(),
    expense_date: z.string(),
    paid_by_id: z.coerce.number(),
    split_type: z.enum(['equal', 'percentage', 'shares', 'exact']),
    participant_ids: z.array(z.coerce.number()).min(1, 'At least one participant required'),
    splits: z.array(z.object({
      user_id: z.coerce.number(),
      percentage_value: z.coerce.number().optional(),
      shares_value: z.coerce.number().optional(),
      exact_amount: z.coerce.number().optional(),
    })).optional(),
    expense_category: z.string(),
    notes: z.string().optional(),
  });

  const { register: regExp, handleSubmit: handleExpSubmit, watch, reset: resetExp } = useForm<any>({
    resolver: zodResolver(expenseFormSchema),
  });

  const watchedSplitType = watch('split_type');
  const watchedParticipants = watch('participant_ids') || [];

  // Handle Edit Expense Prepopulation
  useEffect(() => {
    if (editingExpense) {
      resetExp({
        title: editingExpense.title,
        amount: editingExpense.amount,
        currency: editingExpense.currency,
        expense_date: editingExpense.expense_date,
        paid_by_id: editingExpense.paid_by,
        split_type: editingExpense.split_type,
        participant_ids: editingExpense.splits?.map(s => s.user_id) || [],
        expense_category: editingExpense.expense_category,
        notes: editingExpense.notes,
        splits: editingExpense.splits?.map(s => ({
          user_id: s.user_id,
          percentage_value: s.percentage_value ? parseFloat(s.percentage_value) : undefined,
          shares_value: s.shares_value ? parseFloat(s.shares_value) : undefined,
          exact_amount: s.exact_amount ? parseFloat(s.exact_amount) : undefined,
        })),
      });
      setIsExpenseModalOpen(true);
    }
  }, [editingExpense]);

  // Sync split details array when split type or participants change
  const participantsList = group?.members?.filter(m => watchedParticipants.includes(m.user_id)) || [];

  const handleOpenNewExpense = () => {
    setEditingExpense(null);
    resetExp({
      currency: group?.currency || 'INR',
      expense_date: new Date().toISOString().split('T')[0],
      split_type: 'equal',
      expense_category: 'general',
      participant_ids: group?.members?.map(m => m.user_id) || [],
      paid_by_id: currentUser?.id || '',
    });
    setIsExpenseModalOpen(true);
  };

  const onExpenseSubmit = (data: any) => {
    // Perform split validations before sending to server
    if (data.split_type === 'percentage') {
      const sum = data.splits?.reduce((acc: number, item: any) => acc + (item.percentage_value || 0), 0) || 0;
      if (Math.abs(sum - 100) > 0.01) {
        alert(`Percentages must sum to 100. Current sum: ${sum}%`);
        return;
      }
    } else if (data.split_type === 'exact') {
      const sum = data.splits?.reduce((acc: number, item: any) => acc + (item.exact_amount || 0), 0) || 0;
      if (Math.abs(sum - data.amount) > 0.01) {
        alert(`Exact split values must sum to the total amount (${data.amount} ${data.currency}). Current sum: ${sum}`);
        return;
      }
    } else if (data.split_type === 'shares') {
      const sum = data.splits?.reduce((acc: number, item: any) => acc + (item.shares_value || 0), 0) || 0;
      if (sum <= 0) {
        alert('Total shares must be greater than 0.');
        return;
      }
    }

    const payload: ExpenseInput = {
      group_id: groupId,
      title: data.title,
      amount: data.amount,
      currency: data.currency,
      expense_date: data.expense_date,
      paid_by_id: data.paid_by_id,
      split_type: data.split_type,
      participant_ids: data.participant_ids,
      splits: data.split_type !== 'equal' ? data.splits : undefined,
      expense_category: data.expense_category,
      notes: data.notes || '',
    };

    expenseMutation.mutate(payload);
  };

  // Settlement Form Setup
  const settleSchema = z.object({
    payer_id: z.coerce.number(),
    receiver_id: z.coerce.number(),
    amount: z.coerce.number().positive(),
    currency: z.string(),
    payment_date: z.string(),
    notes: z.string().optional(),
  });

  const { register: regSettle, handleSubmit: handleSettleSubmit, reset: resetSettle } = useForm<any>({
    resolver: zodResolver(settleSchema),
  });

  const onSettleSubmit = (data: any) => {
    if (data.payer_id === data.receiver_id) {
      alert('Payer and receiver cannot be the same person.');
      return;
    }
    settlementMutation.mutate({
      group_id: groupId,
      payer_id: data.payer_id,
      receiver_id: data.receiver_id,
      amount: data.amount,
      currency: data.currency,
      payment_date: data.payment_date,
      notes: data.notes || '',
    });
  };

  // Member Form Setup
  const memberSchema = z.object({
    user_id: z.coerce.number().positive('User ID must be valid'),
    joined_at: z.string(),
  });

  const { register: regMember, handleSubmit: handleMemberSubmit, formState: { errors: memberErrors } } = useForm<any>({
    resolver: zodResolver(memberSchema),
    defaultValues: {
      joined_at: new Date().toISOString().split('T')[0],
    }
  });

  const onMemberSubmit = (data: any) => {
    memberMutation.mutate({ userId: data.user_id, joinedAt: data.joined_at });
  };

  if (groupLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    );
  }

  if (!group) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] space-y-2">
        <AlertCircle className="h-8 w-8 text-slate-400" />
        <p className="text-sm text-slate-500 font-semibold">Group not found.</p>
      </div>
    );
  }

  const currency = group.currency;

  return (
    <div className="space-y-8">
      {/* Group Details Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{group.name}</h1>
            <Badge variant="info">{currency}</Badge>
            {group.is_archived && <Badge variant="error">Archived</Badge>}
          </div>
          <p className="text-sm text-slate-500 font-medium mt-1">{group.description || 'No description provided.'}</p>
        </div>
        
        {/* Actions bar */}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setIsMemberModalOpen(true)} className="text-xs gap-1.5">
            <UserPlus className="h-4 w-4" /> Add Member
          </Button>
          <Button variant="outline" size="sm" onClick={() => {
            resetSettle({
              currency,
              payment_date: new Date().toISOString().split('T')[0],
            });
            setIsSettlementModalOpen(true);
          }} className="text-xs gap-1.5">
            <ArrowRightLeft className="h-4 w-4" /> Record Settlement
          </Button>
          <Button variant="primary" size="sm" onClick={handleOpenNewExpense} className="text-xs gap-1.5">
            <Plus className="h-4 w-4" /> New Expense
          </Button>
        </div>
      </div>

      {/* Tabs list */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-semibold">
        {(['expenses', 'settlements', 'balances', 'trace', 'members'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 border-b-2 capitalize transition-all ${
              activeTab === tab 
                ? 'border-violet-600 text-violet-600' 
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Contents */}
      <div className="mt-6">
        
        {/* EXPENSES TAB */}
        {activeTab === 'expenses' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Expenses Log</CardTitle>
              </CardHeader>
              <CardContent>
                {expensesLoading ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">Loading expenses...</div>
                ) : !expenses || expenses.length === 0 ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">No expenses logged yet.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                          <th className="pb-3">Title</th>
                          <th className="pb-3">Paid By</th>
                          <th className="pb-3">Date</th>
                          <th className="pb-3">Split Type</th>
                          <th className="pb-3 text-right">Amount</th>
                          <th className="pb-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-sm">
                        {expenses.map((e) => (
                          <tr key={e.id} className="hover:bg-slate-50/50">
                            <td className="py-3">
                              <div className="font-semibold text-slate-900">{e.title}</div>
                              {e.notes && <div className="text-[10px] text-slate-400 truncate max-w-xs">{e.notes}</div>}
                            </td>
                            <td className="py-3 text-slate-700">{e.paid_by_username || `User ${e.paid_by}`}</td>
                            <td className="py-3 text-slate-500">{new Date(e.expense_date).toLocaleDateString()}</td>
                            <td className="py-3 capitalize">
                              <Badge variant="default" className="text-[10px]">{e.split_type}</Badge>
                            </td>
                            <td className="py-3 text-right font-bold text-slate-900">
                              {parseFloat(e.amount).toFixed(2)} {e.currency}
                              {e.original_currency !== e.currency && (
                                <div className="text-[10px] text-slate-400 font-medium">Original: {parseFloat(e.original_amount).toFixed(2)} {e.original_currency}</div>
                              )}
                            </td>
                            <td className="py-3 text-right space-x-1.5">
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="text-[10px] px-2 py-1"
                                onClick={() => {
                                  // Fetch detailed expense
                                  getExpense(e.id).then(res => {
                                    setEditingExpense(res);
                                  });
                                }}
                              >
                                Edit
                              </Button>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="text-[10px] px-2 py-1"
                                onClick={() => {
                                  getExpense(e.id).then(res => {
                                    setSelectedSnapshotExpense(res);
                                  });
                                }}
                              >
                                Audits
                              </Button>
                              <button
                                onClick={() => {
                                  if (confirm('Delete this expense?')) {
                                    deleteExpenseMutation.mutate(e.id);
                                  }
                                }}
                                className="text-slate-400 hover:text-red-500 p-1 hover:bg-slate-50 rounded-lg transition-colors"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* SETTLEMENTS TAB */}
        {activeTab === 'settlements' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Direct Settlements Log</CardTitle>
              </CardHeader>
              <CardContent>
                {settlementsLoading ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">Loading settlements...</div>
                ) : !settlements || settlements.length === 0 ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">No settlements logged yet.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                          <th className="pb-3">Reference ID</th>
                          <th className="pb-3">From (Payer)</th>
                          <th className="pb-3">To (Receiver)</th>
                          <th className="pb-3">Date</th>
                          <th className="pb-3 text-right">Amount</th>
                          <th className="pb-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-sm">
                        {settlements.map((s) => (
                          <tr key={s.id} className="hover:bg-slate-50/50">
                            <td className="py-3 font-semibold text-slate-900">{s.reference_id}</td>
                            <td className="py-3 text-slate-700">{s.payer_username || `User ${s.payer}`}</td>
                            <td className="py-3 text-slate-700">{s.receiver_username || `User ${s.receiver}`}</td>
                            <td className="py-3 text-slate-500">{new Date(s.payment_date).toLocaleDateString()}</td>
                            <td className="py-3 text-right font-bold text-slate-900">
                              {parseFloat(s.amount).toFixed(2)} {s.currency}
                            </td>
                            <td className="py-3 text-right">
                              <button
                                onClick={() => {
                                  if (confirm('Delete this settlement?')) {
                                    deleteSettlementMutation.mutate(s.id);
                                  }
                                }}
                                className="text-slate-400 hover:text-red-500 p-1 hover:bg-slate-50 rounded-lg transition-colors"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* BALANCES TAB */}
        {activeTab === 'balances' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Balances Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Net Position Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                      <th className="pb-2">User</th>
                      <th className="pb-2 text-right">Balance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {balances && balances.map((b) => {
                      const val = parseFloat(b.balance);
                      return (
                        <tr key={b.user_id}>
                          <td className="py-3 font-semibold text-slate-900">{b.user}</td>
                          <td className={`py-3 text-right font-bold ${val > 0 ? 'text-green-600' : val < 0 ? 'text-red-600' : 'text-slate-500'}`}>
                            {val > 0 ? '+' : ''}{val.toFixed(2)} {currency}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            {/* Simplified instructions */}
            <Card>
              <CardHeader>
                <CardTitle>Simplified Payback Instructions</CardTitle>
              </CardHeader>
              <CardContent>
                {!simplified || simplified.length === 0 ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">No paybacks needed. Balances settled.</div>
                ) : (
                  <div className="space-y-4">
                    {simplified.map((pay, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-violet-50/50 border border-violet-100 rounded-lg text-sm">
                        <div className="flex items-center space-x-2 font-semibold">
                          <span className="text-red-600">{pay.payer}</span>
                          <span className="text-slate-400 text-xs font-medium">owes</span>
                          <span className="text-green-600">{pay.receiver}</span>
                        </div>
                        <span className="font-bold text-slate-900">{parseFloat(pay.amount).toFixed(2)} {currency}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* LEDGER EXPLAINABILITY TRACE TAB */}
        {activeTab === 'trace' && (
          <div className="space-y-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Running Balance Trace (Rohan's Request)</CardTitle>
                <div className="flex items-center space-x-3 text-xs">
                  <span className="font-semibold text-slate-500">Query User:</span>
                  <select
                    value={selectedTraceUser || ''}
                    onChange={(e) => setSelectedTraceUser(Number(e.target.value))}
                    className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-800"
                  >
                    {group.members?.map((m) => (
                      <option key={m.user_id} value={m.user_id}>{m.username}</option>
                    ))}
                  </select>
                </div>
              </CardHeader>
              <CardContent>
                {!traceData || !traceData.calculation_trace || traceData.calculation_trace.length === 0 ? (
                  <div className="h-20 flex items-center justify-center text-slate-400 text-sm">
                    No transactions affecting this user.
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Running trace timeline */}
                    <div className="relative border-l-2 border-slate-100 ml-4 space-y-6">
                      {traceData.calculation_trace.map((step, idx) => {
                        const deltaVal = parseFloat(step.delta);
                        const runningVal = parseFloat(step.running_balance);
                        return (
                          <div key={idx} className="relative pl-6">
                            {/* Dot icon */}
                            <div className={`absolute -left-[7px] top-1.5 h-3 w-3 rounded-full border-2 bg-white ${
                              deltaVal > 0 ? 'border-green-500' : 'border-red-500'
                            }`} />
                            
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
                              <div>
                                <span className="font-bold text-slate-900">{step.reference_id}</span>
                                <span className="text-slate-400 ml-2">{new Date(step.date).toLocaleDateString()}</span>
                                <div className="text-[10px] text-slate-500 uppercase mt-0.5 font-semibold tracking-wider">{step.event_type} event</div>
                              </div>
                              <div className="flex items-center space-x-6 text-right">
                                <div>
                                  <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Change</div>
                                  <div className={`font-bold ${deltaVal > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {deltaVal > 0 ? '+' : ''}{deltaVal.toFixed(2)} {currency}
                                  </div>
                                </div>
                                <div>
                                  <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Running Balance</div>
                                  <div className="font-extrabold text-slate-900">
                                    {runningVal.toFixed(2)} {currency}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* MEMBERS TAB */}
        {activeTab === 'members' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Group Members</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                        <th className="pb-3">Member Username</th>
                        <th className="pb-3">Role</th>
                        <th className="pb-3">Joined date</th>
                        <th className="pb-3">Leave date</th>
                        <th className="pb-3">Status</th>
                        <th className="pb-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-sm">
                      {group.members?.map((m) => (
                        <tr key={m.id} className="hover:bg-slate-50/50">
                          <td className="py-3 font-semibold text-slate-900">{m.username}</td>
                          <td className="py-3 capitalize text-slate-700">{m.role}</td>
                          <td className="py-3 text-slate-500">{m.joined_at}</td>
                          <td className="py-3 text-slate-500">{m.left_at || '—'}</td>
                          <td className="py-3">
                            {m.is_active ? (
                              <Badge variant="success">Active</Badge>
                            ) : (
                              <Badge variant="default">Inactive</Badge>
                            )}
                          </td>
                          <td className="py-3 text-right">
                            {m.is_active ? (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="text-[10px] py-1 border-red-200 hover:bg-red-50 text-red-600 hover:text-red-700 focus:ring-red-400"
                                onClick={() => setLeavingMember(m)}
                              >
                                Set Leave
                              </Button>
                            ) : (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="text-[10px] py-1"
                                onClick={() => {
                                  // Rejoin member
                                  memberMutation.mutate({
                                    userId: m.user_id,
                                    joinedAt: new Date().toISOString().split('T')[0],
                                  });
                                }}
                              >
                                Rejoin
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

      </div>

      {/* CREATE / EDIT EXPENSE MODAL */}
      <Dialog
        isOpen={isExpenseModalOpen}
        onClose={() => setIsExpenseModalOpen(false)}
        title={editingExpense ? 'Edit Expense' : 'Create Expense'}
      >
        <form onSubmit={handleExpSubmit(onExpenseSubmit)} className="space-y-4">
          <Input
            label="Title / Description"
            placeholder="e.g. Electricity Bill"
            {...regExp('title')}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Amount"
              type="number"
              step="0.01"
              placeholder="0.00"
              {...regExp('amount')}
            />

            <div className="flex flex-col space-y-1">
              <label className="text-xs font-semibold text-slate-600 tracking-wide">Category</label>
              <select
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
                {...regExp('expense_category')}
              >
                <option value="general">General</option>
                <option value="food">Food</option>
                <option value="rent">Rent</option>
                <option value="utilities">Utilities</option>
                <option value="travel">Travel</option>
                <option value="groceries">Groceries</option>
                <option value="entertainment">Entertainment</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col space-y-1">
              <label className="text-xs font-semibold text-slate-600 tracking-wide">Paid By</label>
              <select
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
                {...regExp('paid_by_id')}
              >
                {group.members?.filter(m => m.is_active).map(m => (
                  <option key={m.user_id} value={m.user_id}>{m.username}</option>
                ))}
              </select>
            </div>

            <Input
              label="Date"
              type="date"
              {...regExp('expense_date')}
            />
          </div>

          <div className="flex flex-col space-y-2 border-t border-b border-slate-100 py-3">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">Participants</label>
            <div className="flex flex-wrap gap-3">
              {group.members?.map(m => (
                <label key={m.user_id} className="flex items-center space-x-2 text-xs font-medium text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 cursor-pointer hover:bg-slate-100 transition-colors">
                  <input
                    type="checkbox"
                    value={m.user_id}
                    className="rounded text-violet-600 focus:ring-violet-500"
                    {...regExp('participant_ids')}
                  />
                  <span>{m.username}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">Split Type</label>
            <select
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
              {...regExp('split_type')}
            >
              <option value="equal">Equal split</option>
              <option value="percentage">Percentage shares</option>
              <option value="shares">Shares weight</option>
              <option value="exact">Exact amounts</option>
            </select>
          </div>

          {/* DYNAMIC SPLITS INPUTS */}
          {watchedSplitType !== 'equal' && participantsList.length > 0 && (
            <div className="space-y-3 border border-slate-100 rounded-xl p-4 bg-slate-50/50">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Enter Splits Details</label>
              {participantsList.map((user, idx) => (
                <div key={user.user_id} className="flex items-center justify-between gap-4 text-xs">
                  <span className="font-semibold text-slate-700">{user.username}</span>
                  <input
                    type="hidden"
                    value={user.user_id}
                    {...regExp(`splits.${idx}.user_id`)}
                  />
                  
                  {watchedSplitType === 'percentage' && (
                    <div className="flex items-center gap-1.5">
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="%"
                        className="w-24 text-right"
                        {...regExp(`splits.${idx}.percentage_value`)}
                      />
                      <span className="text-slate-400 font-semibold">%</span>
                    </div>
                  )}

                  {watchedSplitType === 'shares' && (
                    <div className="flex items-center gap-1.5">
                      <Input
                        type="number"
                        step="1"
                        placeholder="Shares"
                        className="w-24 text-right"
                        {...regExp(`splits.${idx}.shares_value`)}
                      />
                      <span className="text-slate-400 font-semibold">shares</span>
                    </div>
                  )}

                  {watchedSplitType === 'exact' && (
                    <div className="flex items-center gap-1.5">
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="0.00"
                        className="w-28 text-right"
                        {...regExp(`splits.${idx}.exact_amount`)}
                      />
                      <span className="text-slate-400 font-semibold">{currency}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button variant="outline" type="button" onClick={() => setIsExpenseModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={expenseMutation.isPending}>
              {editingExpense ? 'Save Changes' : 'Create Expense'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* RECORD SETTLEMENT MODAL */}
      <Dialog
        isOpen={isSettlementModalOpen}
        onClose={() => setIsSettlementModalOpen(false)}
        title="Record Settlement"
      >
        <form onSubmit={handleSettleSubmit(onSettleSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col space-y-1">
              <label className="text-xs font-semibold text-slate-600 tracking-wide">From (Payer)</label>
              <select
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
                {...regSettle('payer_id')}
              >
                <option value="">Select Payer</option>
                {group.members?.filter(m => m.is_active).map(m => (
                  <option key={m.user_id} value={m.user_id}>{m.username}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col space-y-1">
              <label className="text-xs font-semibold text-slate-600 tracking-wide">To (Receiver)</label>
              <select
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
                {...regSettle('receiver_id')}
              >
                <option value="">Select Receiver</option>
                {group.members?.filter(m => m.is_active).map(m => (
                  <option key={m.user_id} value={m.user_id}>{m.username}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Amount"
              type="number"
              step="0.01"
              placeholder="0.00"
              {...regSettle('amount')}
            />

            <Input
              label="Payment Date"
              type="date"
              {...regSettle('payment_date')}
            />
          </div>

          <Input
            label="Notes"
            placeholder="e.g. February cash repayment"
            {...regSettle('notes')}
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" type="button" onClick={() => setIsSettlementModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={settlementMutation.isPending}>
              Record Settlement
            </Button>
          </div>
        </form>
      </Dialog>

      {/* ADD MEMBER MODAL */}
      <Dialog
        isOpen={isMemberModalOpen}
        onClose={() => setIsMemberModalOpen(false)}
        title="Add Group Member"
      >
        <form onSubmit={handleMemberSubmit(onMemberSubmit)} className="space-y-4">
          <Input
            label="User DB ID"
            type="number"
            placeholder="e.g. 1"
            error={memberErrors.user_id?.message as string | undefined}
            {...regMember('user_id')}
          />

          <Input
            label="Join Date"
            type="date"
            error={memberErrors.joined_at?.message as string | undefined}
            {...regMember('joined_at')}
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" type="button" onClick={() => setIsMemberModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={memberMutation.isPending}>
              Add Member
            </Button>
          </div>
        </form>
      </Dialog>

      {/* LEAVE GROUP MODAL */}
      <Dialog
        isOpen={leavingMember !== null}
        onClose={() => setLeavingMember(null)}
        title={`Member Leave: ${leavingMember?.username}`}
      >
        <div className="space-y-4">
          <Input
            label="Departure Date (left_at)"
            type="date"
            value={leaveDate}
            onChange={(e) => setLeaveDate(e.target.value)}
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" type="button" onClick={() => setLeavingMember(null)}>
              Cancel
            </Button>
            <Button 
              variant="danger" 
              onClick={() => {
                if (leavingMember) {
                  leaveMutation.mutate({
                    membershipId: leavingMember.id,
                    leftAt: leaveDate,
                  });
                }
              }}
              isLoading={leaveMutation.isPending}
            >
              Confirm Deactivation
            </Button>
          </div>
        </div>
      </Dialog>

      {/* AUDITS SNAPSHOTS LOG MODAL */}
      <Dialog
        isOpen={selectedSnapshotExpense !== null}
        onClose={() => setSelectedSnapshotExpense(null)}
        title={`Audit Trail: ${selectedSnapshotExpense?.title}`}
      >
        <div className="space-y-4">
          {!selectedSnapshotExpense?.snapshots || selectedSnapshotExpense.snapshots.length === 0 ? (
            <div className="text-slate-400 text-sm text-center py-6">No snapshots saved.</div>
          ) : (
            <div className="space-y-4 divide-y divide-slate-100">
              {selectedSnapshotExpense.snapshots.map((snap) => (
                <div key={snap.id} className="pt-4 first:pt-0">
                  <div className="flex justify-between items-center text-xs font-semibold mb-2">
                    <Badge variant="info">Version {snap.version}</Badge>
                    <span className="text-slate-400">{new Date(snap.created_at).toLocaleString()}</span>
                  </div>
                  <pre className="text-[10px] bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto max-h-[150px]">
                    {JSON.stringify(snap.payload_json, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end pt-4 border-t border-slate-100">
            <Button variant="outline" onClick={() => setSelectedSnapshotExpense(null)}>
              Close Audit Trail
            </Button>
          </div>
        </div>
      </Dialog>

    </div>
  );
};
export default GroupDetails;
