import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listGroups, createGroup, archiveGroup } from '../api/groups';
import type { Group } from '../api/groups';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Dialog } from '../components/ui/Dialog';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Users, Calendar, Plus, Archive, ExternalLink, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const groupSchema = z.object({
  name: z.string().min(1, 'Group name is required').max(100, 'Name too long'),
  description: z.string().optional(),
  currency: z.enum(['INR', 'USD', 'EUR', 'GBP']),
});

type GroupFormValues = z.infer<typeof groupSchema>;

export const Groups: React.FC = () => {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Fetch groups
  const { data: groups, isLoading, error } = useQuery<Group[]>({
    queryKey: ['groups', showArchived],
    queryFn: () => listGroups(showArchived),
  });

  // Create Group Mutation
  const createMutation = useMutation({
    mutationFn: (data: GroupFormValues) => createGroup(data.name, data.description || '', data.currency),
    onSuccess: (newGroup) => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      setIsModalOpen(false);
      reset();
      
      // Auto set this group as active on create
      sessionStorage.setItem('spreewise_active_group_id', newGroup.id.toString());
      window.dispatchEvent(new Event('storage'));
    },
  });

  // Archive Group Mutation
  const archiveMutation = useMutation({
    mutationFn: (id: number) => archiveGroup(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      // Clear active group if archived
      const currentActive = sessionStorage.getItem('spreewise_active_group_id');
      if (currentActive) {
        queryClient.invalidateQueries({ queryKey: ['group'] });
        window.dispatchEvent(new Event('storage'));
      }
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: {
      currency: 'INR',
    },
  });

  const onSubmit = (data: GroupFormValues) => {
    createMutation.mutate(data);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Groups</h1>
          <p className="text-sm text-slate-500 font-medium">Manage your shared expense spaces</p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowArchived(!showArchived)}
            className="text-xs"
          >
            {showArchived ? 'Hide Archived' : 'Show Archived'}
          </Button>
          <Button 
            variant="primary" 
            size="sm"
            onClick={() => setIsModalOpen(true)}
            className="text-xs gap-1.5"
          >
            <Plus className="h-4 w-4" /> New Group
          </Button>
        </div>
      </div>

      {/* Grid List */}
      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
        </div>
      ) : error ? (
        <div className="rounded-xl bg-red-50 border border-red-200 p-6 flex items-start space-x-3 text-red-700 text-sm">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <p className="font-semibold">Failed to fetch groups. Make sure the server is accessible.</p>
        </div>
      ) : !groups || groups.length === 0 ? (
        <div className="flex h-40 flex-col items-center justify-center border border-dashed border-slate-200 rounded-xl space-y-2 text-slate-400">
          <AlertCircle className="h-8 w-8 text-slate-300" />
          <p className="text-sm font-semibold">No groups found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {groups.map((g) => (
            <Card key={g.id} className="relative group hover:border-violet-300 hover:shadow-md transition-all flex flex-col justify-between">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge variant={g.is_archived ? 'default' : 'info'}>
                    {g.currency}
                  </Badge>
                  {g.is_archived && (
                    <Badge variant="error" className="text-[10px]">Archived</Badge>
                  )}
                </div>
                <CardTitle className="mt-4 text-slate-900 group-hover:text-violet-600 transition-colors flex items-center justify-between">
                  <Link to={`/groups/${g.id}`} className="hover:underline flex items-center gap-1.5">
                    {g.name} <ExternalLink className="h-4 w-4 text-slate-400" />
                  </Link>
                </CardTitle>
                {g.description && (
                  <p className="text-xs text-slate-400 font-medium line-clamp-2 mt-1.5">
                    {g.description}
                  </p>
                )}
              </CardHeader>
              
              <CardContent className="border-t border-slate-100 pt-4 mt-auto flex items-center justify-between text-slate-500 text-xs font-semibold">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" /> {g.active_member_count || 0}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" /> {new Date(g.created_at).toLocaleDateString()}
                  </span>
                </div>
                {!g.is_archived && (
                  <button
                    onClick={() => {
                      if (confirm(`Are you sure you want to archive group "${g.name}"?`)) {
                        archiveMutation.mutate(g.id);
                      }
                    }}
                    className="text-slate-400 hover:text-red-500 p-1 hover:bg-slate-50 rounded-lg transition-colors"
                    title="Archive Group"
                  >
                    <Archive className="h-4 w-4" />
                  </button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Group Modal */}
      <Dialog
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Group"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <Input
            label="Group Name"
            placeholder="e.g. Flat 202 Bills"
            error={errors.name?.message}
            {...register('name')}
          />

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">
              Description (Optional)
            </label>
            <textarea
              placeholder="e.g. Shared grocery and rent log"
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 transition-all focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent min-h-[80px]"
              {...register('description')}
            />
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">
              Default Group Currency
            </label>
            <select
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 transition-all focus:outline-none focus:ring-2 focus:ring-violet-500"
              {...register('currency')}
            >
              <option value="INR">INR (₹)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={createMutation.isPending}>
              Create Group
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
};
export default Groups;
