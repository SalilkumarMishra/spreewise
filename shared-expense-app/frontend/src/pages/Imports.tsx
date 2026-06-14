import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listImportJobs, uploadCSV } from '../api/imports';
import type { ImportJob } from '../api/imports';
import { listGroups } from '../api/groups';
import type { Group } from '../api/groups';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { FileSpreadsheet, Upload, Calendar, FileText, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Imports: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Queries
  const { data: jobs, isLoading: jobsLoading } = useQuery<ImportJob[]>({
    queryKey: ['import-jobs'],
    queryFn: listImportJobs,
  });

  const { data: groups } = useQuery<Group[]>({
    queryKey: ['groups'],
    queryFn: () => listGroups(false),
  });

  // Automatically select first group
  React.useEffect(() => {
    if (groups && groups.length > 0 && !selectedGroupId) {
      setSelectedGroupId(groups[0].id);
    }
  }, [groups, selectedGroupId]);

  // Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: (input: { groupId: number, file: File }) => uploadCSV(input.groupId, input.file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['import-jobs'] });
      setSelectedFile(null);
      // Reset input element
      const fileInput = document.getElementById('csv-file') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'CSV upload failed. Verify columns are correct.');
    }
  });

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGroupId) {
      alert('Please select a target group.');
      return;
    }
    if (!selectedFile) {
      alert('Please choose a CSV file to upload.');
      return;
    }
    uploadMutation.mutate({
      groupId: selectedGroupId,
      file: selectedFile,
    });
  };

  const getStatusBadgeVariant = (status: ImportJob['status']) => {
    switch (status) {
      case 'completed': return 'success';
      case 'review_required': return 'warning';
      case 'failed': return 'error';
      case 'processing': return 'info';
      default: return 'default';
    }
  };

  const formatStatus = (status: string) => {
    return status.replace('_', ' ');
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">CSV Ingestion Engine</h1>
        <p className="text-sm text-slate-500 font-medium">Upload historical logs and audit duplicates or currency differences</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Upload Form Panel */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Ingest CSV File</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUploadSubmit} className="space-y-4">
              
              <div className="flex flex-col space-y-1">
                <label className="text-xs font-semibold text-slate-600 tracking-wide">Target Group</label>
                <select
                  value={selectedGroupId || ''}
                  onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  {groups && groups.map((g) => (
                    <option key={g.id} value={g.id}>{g.name} ({g.currency})</option>
                  ))}
                  {!groups || groups.length === 0 ? (
                    <option value="">No Active Groups</option>
                  ) : null}
                </select>
              </div>

              <div className="flex flex-col space-y-2">
                <label className="text-xs font-semibold text-slate-600 tracking-wide">Select CSV file</label>
                <div className="border border-dashed border-slate-200 rounded-lg p-6 bg-slate-50/50 flex flex-col items-center justify-center space-y-2 cursor-pointer hover:bg-slate-50 transition-all relative">
                  <Upload className="h-8 w-8 text-slate-400" />
                  <span className="text-xs text-slate-600 font-semibold truncate max-w-[200px]">
                    {selectedFile ? selectedFile.name : 'Choose File (CSV only)'}
                  </span>
                  <input
                    id="csv-file"
                    type="file"
                    accept=".csv"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                </div>
              </div>

              <Button
                type="submit"
                variant="primary"
                className="w-full py-2.5"
                isLoading={uploadMutation.isPending}
              >
                Upload & Ingest
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* History Log list */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Historical Import Jobs</CardTitle>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['import-jobs'] })}
              className="p-2"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="h-40 flex items-center justify-center text-slate-400 text-sm">Loading import history...</div>
            ) : !jobs || jobs.length === 0 ? (
              <div className="h-40 flex flex-col items-center justify-center text-slate-400 text-sm border border-dashed border-slate-100 rounded-xl space-y-2">
                <FileSpreadsheet className="h-8 w-8 text-slate-300" />
                <span>No import logs captured yet</span>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase">
                      <th className="pb-3">Filename</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">Uploaded</th>
                      <th className="pb-3 text-right">Rows</th>
                      <th className="pb-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {jobs.map((j) => (
                      <tr key={j.id} className="hover:bg-slate-50/50">
                        <td className="py-3 font-semibold text-slate-900">{j.original_filename}</td>
                        <td className="py-3 capitalize">
                          <Badge variant={getStatusBadgeVariant(j.status)}>
                            {formatStatus(j.status)}
                          </Badge>
                        </td>
                        <td className="py-3 text-slate-500 text-xs font-semibold">
                          <span className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5" />
                            {new Date(j.created_at).toLocaleString()}
                          </span>
                        </td>
                        <td className="py-3 text-right text-slate-600 font-semibold">{j.row_count} rows</td>
                        <td className="py-3 text-right">
                          <Link 
                            to={`/imports/${j.id}`}
                            className="inline-flex items-center text-violet-600 hover:text-violet-700 text-xs font-bold gap-1"
                          >
                            Open <FileText className="h-3.5 w-3.5" />
                          </Link>
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
    </div>
  );
};
export default Imports;
