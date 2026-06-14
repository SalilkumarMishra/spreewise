import React, { useEffect, useState } from 'react';
import { Navigate, Outlet, Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { listGroups } from '../api/groups';
import type { Group } from '../api/groups';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard, Users, FileSpreadsheet, LogOut, ArrowRightLeft,
  UserPlus, Hash, ChevronDown
} from 'lucide-react';

export const ProtectedLayout: React.FC = () => {
  const { isAuthenticated, user, logoutAction, isLoading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [activeGroupId, setActiveGroupId] = useState<number | null>(null);

  // Sync active group id from sessionStorage
  useEffect(() => {
    const savedId = sessionStorage.getItem('spreewise_active_group_id');
    if (savedId) {
      setActiveGroupId(Number(savedId));
    }
  }, []);

  // Fetch groups (now membership-scoped by backend)
  const { data: groups } = useQuery<Group[]>({
    queryKey: ['groups'],
    queryFn: () => listGroups(false),
    enabled: isAuthenticated,
  });

  // Automatically select the first group if none is selected yet
  useEffect(() => {
    if (groups && groups.length > 0 && !activeGroupId) {
      const firstId = groups[0].id;
      setActiveGroupId(firstId);
      sessionStorage.setItem('spreewise_active_group_id', firstId.toString());
    }
  }, [groups, activeGroupId]);

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-violet-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-500">Loading Spreewise...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const handleGroupChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = Number(e.target.value);
    setActiveGroupId(newId);
    sessionStorage.setItem('spreewise_active_group_id', newId.toString());
    window.dispatchEvent(new Event('storage'));
  };

  // Get the current user's role in the active group
  const activeGroup = groups?.find((g) => g.id === activeGroupId);
  const currentRole = activeGroup?.current_user_role;

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Groups', path: '/groups', icon: Users },
    { name: 'CSV Imports', path: '/imports', icon: FileSpreadsheet },
  ];

  // User initials for avatar
  const initials = user
    ? ((user.first_name?.[0] || '') + (user.last_name?.[0] || '') || user.username?.[0] || '?').toUpperCase()
    : '?';

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-400 flex flex-col justify-between border-r border-slate-800">
        <div>
          {/* Logo / Branding */}
          <div className="h-16 flex items-center px-6 border-b border-slate-800 space-x-2">
            <div className="bg-violet-600 p-1.5 rounded-lg text-white">
              <ArrowRightLeft className="h-5 w-5" />
            </div>
            <span className="text-white font-bold text-lg tracking-tight">Spreewise</span>
          </div>

          {/* Navigation items */}
          <nav className="mt-6 px-4 space-y-1">
            {navItems.map((item) => {
              const isActive = location.pathname.startsWith(item.path);
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.path}
                  className={`flex items-center px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-violet-600 text-white shadow-md shadow-violet-600/10'
                      : 'hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Icon className={`h-4 w-4 mr-3 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                  {item.name}
                </Link>
              );
            })}

            {/* Divider */}
            <div className="pt-4 pb-2">
              <p className="px-4 text-[10px] font-bold uppercase tracking-widest text-slate-600">Quick Actions</p>
            </div>

            <Link
              to="/join-group"
              className={`flex items-center px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                location.pathname === '/join-group'
                  ? 'bg-violet-600 text-white'
                  : 'hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Hash className="h-4 w-4 mr-3 text-slate-400" />
              Join Group
            </Link>

            <Link
              to="/signup"
              className="flex items-center px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 hover:text-white transition-all"
              onClick={(e) => {
                // Signup while logged in — navigate to groups create instead
                e.preventDefault();
                navigate('/groups');
              }}
            >
              <UserPlus className="h-4 w-4 mr-3 text-slate-400" />
              Invite to Spreewise
            </Link>
          </nav>
        </div>

        {/* Sidebar Footer — user info */}
        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center space-x-3">
            {/* Avatar */}
            <div className="h-8 w-8 rounded-full bg-violet-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-xs font-semibold truncate">{user?.full_name || user?.username}</p>
              <p className="text-[10px] text-slate-500 truncate">
                {currentRole ? `${currentRole} · ` : ''}{user?.username}
              </p>
            </div>
            <button
              onClick={async () => {
                await logoutAction();
                navigate('/login');
              }}
              className="text-slate-500 hover:text-red-400 p-1.5 hover:bg-slate-800 rounded-lg transition-all"
              title="Log Out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between z-10">
          <div className="flex items-center space-x-4">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Group</label>
            <div className="relative">
              <select
                value={activeGroupId || ''}
                onChange={handleGroupChange}
                className="appearance-none bg-slate-50 border border-slate-200 rounded-lg pl-3 pr-8 py-1.5 text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {groups && groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.currency})
                  </option>
                ))}
                {!groups || groups.length === 0 ? (
                  <option value="">No Active Groups</option>
                ) : null}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            </div>
            {currentRole && (
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                currentRole === 'owner'
                  ? 'bg-violet-100 text-violet-700'
                  : currentRole === 'admin'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-slate-100 text-slate-600'
              }`}>
                {currentRole.toUpperCase()}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs font-medium text-slate-400">Connected</span>
          </div>
        </header>

        {/* Main Route Body */}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet context={{ activeGroupId }} />
        </main>
      </div>
    </div>
  );
};
export default ProtectedLayout;
