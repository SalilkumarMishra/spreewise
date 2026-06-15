import React, { useEffect } from 'react';
import { useOutletContext, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { getGroupBalances, getUserExplanation } from '../api/balances';
import { listExpenses } from '../api/expenses';
import { getGroup } from '../api/groups';
import { getDashboard } from '../api/dashboard';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ArrowUpRight, ArrowDownRight, Wallet, Users, AlertCircle, TrendingDown, TrendingUp, Scale, FileWarning } from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';


export const Dashboard: React.FC = () => {
  const { activeGroupId } = useOutletContext<{ activeGroupId: number | null }>();
  const { user } = useAuth();

  // Force re-fetch when storage changes (active group select)
  const [, forceUpdate] = React.useReducer((x) => x + 1, 0);
  useEffect(() => {
    const handleStorageChange = () => {
      forceUpdate();
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Fetch personal dashboard summary (cross-group overview)
  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    enabled: true,
  });

  // Fetch active group metadata
  const { data: group } = useQuery({
    queryKey: ['group', activeGroupId],
    queryFn: () => getGroup(activeGroupId!),
    enabled: !!activeGroupId,
  });

  // Fetch balances
  const { data: balances, isLoading: balancesLoading } = useQuery({
    queryKey: ['balances', activeGroupId],
    queryFn: () => getGroupBalances(activeGroupId!),
    enabled: !!activeGroupId,
  });

  // Fetch user specific balance details (Rohan + Sam requirements)
  const { data: userExplanation } = useQuery({
    queryKey: ['explanation', activeGroupId, user?.id],
    queryFn: () => getUserExplanation(activeGroupId!, user!.id),
    enabled: !!activeGroupId && !!user?.id && user.id > 0,
  });

  // Fetch expenses to compile charts data
  const { data: expenses } = useQuery({
    queryKey: ['expenses', activeGroupId],
    queryFn: () => listExpenses(activeGroupId!),
    enabled: !!activeGroupId,
  });

  // Process category breakdown for charts
  const categoryData = React.useMemo(() => {
    if (!expenses) return [];
    const breakdown: Record<string, number> = {};
    expenses.forEach((e) => {
      const cat = e.expense_category || 'general';
      const amt = parseFloat(e.amount);
      breakdown[cat] = (breakdown[cat] || 0) + amt;
    });
    return Object.entries(breakdown).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value: parseFloat(value.toFixed(2)),
    }));
  }, [expenses]);

  // Process timeline expenses for charts (group by month/date)
  const timelineData = React.useMemo(() => {
    if (!expenses) return [];
    const monthly: Record<string, number> = {};
    expenses.forEach((e) => {
      const date = new Date(e.expense_date);
      const label = date.toLocaleString('default', { month: 'short', year: 'numeric' });
      monthly[label] = (monthly[label] || 0) + parseFloat(e.amount);
    });
    return Object.entries(monthly)
      .map(([name, total]) => ({ name, total: parseFloat(total.toFixed(2)) }))
      .reverse(); // Chronological order
  }, [expenses]);

  if (!activeGroupId) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center space-y-4">
        <AlertCircle className="h-12 w-12 text-slate-400" />
        <h3 className="text-lg font-semibold text-slate-900">No Active Group Selected</h3>
        <p className="text-sm text-slate-500 max-w-sm text-center">
          Spreewise operates inside groups. Select an active group from the header selector above, or create a new one.
        </p>
        <Link to="/groups" className="text-violet-600 hover:text-violet-700 text-sm font-semibold underline">
          Go to Groups
        </Link>
      </div>
    );
  }

  const netBalance = parseFloat(userExplanation?.net_balance || '0.00');
  const currency = group?.currency || 'INR';

  // Pie chart colors
  const COLORS = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#64748b'];

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
        <p className="text-sm text-slate-500">
          Welcome back, <span className="font-semibold text-violet-600">{user?.full_name || user?.username}</span>
          {group ? ` · Viewing ${group.name}` : ''}
        </p>
      </div>

      {/* Personal Overview — cross-group summary */}
      {dashboardData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* You Owe */}
          <div className="bg-red-50 border border-red-100 rounded-xl p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-red-500 uppercase tracking-wide">You Owe</p>
              <p className="text-2xl font-bold text-red-700 mt-1">
                ₹{dashboardData.net_balance.you_owe.toFixed(2)}
              </p>
              <p className="text-[11px] text-red-400 mt-1">across {dashboardData.group_count} group{dashboardData.group_count !== 1 ? 's' : ''}</p>
            </div>
            <div className="bg-red-100 p-3 rounded-xl">
              <TrendingDown className="h-6 w-6 text-red-500" />
            </div>
          </div>

          {/* You Are Owed */}
          <div className="bg-green-50 border border-green-100 rounded-xl p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-green-600 uppercase tracking-wide">You Are Owed</p>
              <p className="text-2xl font-bold text-green-700 mt-1">
                ₹{dashboardData.net_balance.you_are_owed.toFixed(2)}
              </p>
              <p className="text-[11px] text-green-400 mt-1">across your active groups</p>
            </div>
            <div className="bg-green-100 p-3 rounded-xl">
              <TrendingUp className="h-6 w-6 text-green-500" />
            </div>
          </div>

          {/* Net Balance */}
          <div className={`border rounded-xl p-5 flex items-center justify-between ${
            dashboardData.net_balance.net >= 0
              ? 'bg-violet-50 border-violet-100'
              : 'bg-orange-50 border-orange-100'
          }`}>
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Net Balance</p>
              <p className={`text-2xl font-bold mt-1 ${
                dashboardData.net_balance.net >= 0 ? 'text-violet-700' : 'text-orange-700'
              }`}>
                {dashboardData.net_balance.net >= 0 ? '+' : ''}₹{dashboardData.net_balance.net.toFixed(2)}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">overall position</p>
            </div>
            <div className={`p-3 rounded-xl ${
              dashboardData.net_balance.net >= 0 ? 'bg-violet-100' : 'bg-orange-100'
            }`}>
              <Scale className={`h-6 w-6 ${
                dashboardData.net_balance.net >= 0 ? 'text-violet-500' : 'text-orange-500'
              }`} />
            </div>
          </div>
        </div>
      )}

      {/* Pending import reviews alert */}
      {dashboardData && dashboardData.pending_import_reviews > 0 && (
        <div className="flex items-center space-x-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <FileWarning className="h-5 w-5 text-amber-500 shrink-0" />
          <p className="text-sm text-amber-700 font-medium">
            {dashboardData.pending_import_reviews} import job{dashboardData.pending_import_reviews !== 1 ? 's' : ''} awaiting your review.
          </p>
          <Link to="/imports" className="ml-auto text-sm font-semibold text-amber-600 hover:underline">Review now →</Link>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Net Position Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Net Position</p>
                <h3 className="text-2xl font-bold text-slate-900 mt-2">
                  {netBalance >= 0 ? '+' : ''}{netBalance.toFixed(2)} {currency}
                </h3>
              </div>
              <div className={`p-3 rounded-xl ${netBalance >= 0 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                {netBalance >= 0 ? <ArrowUpRight className="h-6 w-6" /> : <ArrowDownRight className="h-6 w-6" />}
              </div>
            </div>
            <div className="mt-4 flex items-center space-x-1.5 text-xs">
              <span className={netBalance >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                {netBalance >= 0 ? 'Settled / Lent' : 'Owes money'}
              </span>
              <span className="text-slate-400">in this group</span>
            </div>
          </CardContent>
        </Card>

        {/* Total Paid Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Total Amount Paid</p>
                <h3 className="text-2xl font-bold text-slate-900 mt-2">
                  {parseFloat(userExplanation?.total_paid || '0.00').toFixed(2)} {currency}
                </h3>
              </div>
              <div className="p-3 rounded-xl bg-violet-50 text-violet-600">
                <Wallet className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center space-x-1.5 text-xs">
              <span className="text-violet-600 font-semibold">
                {parseFloat(userExplanation?.total_owed || '0.00').toFixed(2)} {currency}
              </span>
              <span className="text-slate-400">total share owed</span>
            </div>
          </CardContent>
        </Card>

        {/* Members Count Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Members</p>
                <h3 className="text-2xl font-bold text-slate-900 mt-2">
                  {group?.active_member_count || 0} / {group?.total_member_count || 0}
                </h3>
              </div>
              <div className="p-3 rounded-xl bg-blue-50 text-blue-600">
                <Users className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center space-x-1.5 text-xs">
              <span className="text-blue-600 font-semibold">Active Members</span>
              <span className="text-slate-400">rejoining preserved</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Visual Analytics & Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Timeline Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Group Expenses Timeline</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {timelineData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                No monthly transactions recorded yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timelineData}>
                  <XAxis dataKey="name" stroke="#888888" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#888888" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}`} />
                  <Tooltip formatter={(value) => [`${value} ${currency}`, 'Expenses']} />
                  <Bar dataKey="total" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Category Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Category Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="h-72 flex flex-col justify-between">
            {categoryData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                No expense category logged
              </div>
            ) : (
              <>
                <div className="h-[200px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={categoryData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={75}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {categoryData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `${value} ${currency}`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-semibold text-slate-500 mt-2">
                  {categoryData.slice(0, 4).map((entry, index) => (
                    <div key={entry.name} className="flex items-center space-x-1.5">
                      <div className="h-3.5 w-3.5 rounded" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                      <span className="truncate">{entry.name}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Group Balances list */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Member Net Balances</CardTitle>
          <Badge variant="info">Summary</Badge>
        </CardHeader>
        <CardContent>
          {balancesLoading ? (
            <div className="h-20 flex items-center justify-center text-slate-400 text-sm">
              Loading group balance sheets...
            </div>
          ) : !balances || balances.length === 0 ? (
            <div className="h-20 flex items-center justify-center text-slate-400 text-sm">
              No balances computed. Create a membership or expense.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                    <th className="pb-3">User</th>
                    <th className="pb-3 text-right">Net Position</th>
                    <th className="pb-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {balances.map((b) => {
                    const balanceVal = parseFloat(b.balance);
                    return (
                      <tr key={b.user_id} className="hover:bg-slate-50/50">
                        <td className="py-3 font-semibold text-slate-900">{b.user} {b.user_id === user?.id && '(You)'}</td>
                        <td className={`py-3 text-right font-bold ${balanceVal > 0 ? 'text-green-600' : balanceVal < 0 ? 'text-red-600' : 'text-slate-500'}`}>
                          {balanceVal > 0 ? '+' : ''}{balanceVal.toFixed(2)} {currency}
                        </td>
                        <td className="py-3 text-right">
                          {balanceVal > 0 ? (
                            <Badge variant="success">Lent</Badge>
                          ) : balanceVal < 0 ? (
                            <Badge variant="error">Owes</Badge>
                          ) : (
                            <Badge variant="default">Settled</Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
export default Dashboard;
