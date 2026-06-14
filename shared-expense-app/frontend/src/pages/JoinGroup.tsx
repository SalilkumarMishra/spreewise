import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { joinGroupByInviteCode } from '../api/groups';
import { ArrowRightLeft, Hash, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react';

const JoinGroup: React.FC = () => {
  const navigate = useNavigate();
  const [inviteCode, setInviteCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ groupId: number; groupName?: string } | null>(null);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteCode.trim()) {
      setError('Please enter an invite code.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await joinGroupByInviteCode(inviteCode.trim().toUpperCase());
      setSuccess({ groupId: result.group_id });
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.response?.data?.invite_code?.[0];
      setError(typeof detail === 'string' ? detail : 'Invalid invite code. Please check and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-md bg-white p-8 border border-slate-200 rounded-2xl shadow-xl text-center space-y-6">
          <div className="flex justify-center">
            <div className="bg-green-100 p-4 rounded-full">
              <CheckCircle className="h-12 w-12 text-green-500" />
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">You've joined the group!</h2>
            <p className="mt-2 text-slate-500 text-sm">Welcome to the group. You can now view expenses and balances.</p>
          </div>
          <div className="flex flex-col space-y-3">
            <Button
              variant="primary"
              className="w-full"
              onClick={() => navigate(`/groups/${success.groupId}`)}
            >
              <ArrowRight className="h-4 w-4 mr-2 inline" />
              Go to Group
            </Button>
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => navigate('/dashboard')}
            >
              Back to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white p-8 border border-slate-200 rounded-2xl shadow-xl space-y-8">
        {/* Branding */}
        <div className="flex flex-col items-center">
          <div className="bg-violet-600 p-3 rounded-2xl text-white shadow-lg shadow-violet-600/10">
            <ArrowRightLeft className="h-8 w-8" />
          </div>
          <h1 className="mt-6 text-center text-3xl font-extrabold tracking-tight text-slate-900">
            Join a Group
          </h1>
          <p className="mt-2 text-center text-sm text-slate-500">
            Enter the invite code shared by your group owner
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4 flex items-start space-x-3 text-red-700 text-sm">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <p className="font-medium">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleJoin} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Invite Code
            </label>
            <div className="relative">
              <Hash className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                id="invite_code"
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                placeholder="SPW-AB12CD34"
                className="w-full pl-9 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 uppercase"
                maxLength={12}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <p className="mt-1.5 text-xs text-slate-400">
              Format: SPW-XXXXXXXX (case-insensitive)
            </p>
          </div>

          <Button
            type="submit"
            variant="primary"
            className="w-full py-2.5"
            isLoading={isLoading}
          >
            Join Group
          </Button>
        </form>

        {/* Links */}
        <div className="text-center space-y-2">
          <p className="text-sm text-slate-500">
            <Link to="/dashboard" className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
              Back to Dashboard
            </Link>
          </p>
          <p className="text-sm text-slate-500">
            Want to create your own group?{' '}
            <Link to="/groups" className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
              Go to Groups
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default JoinGroup;
