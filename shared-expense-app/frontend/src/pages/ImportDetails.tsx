import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getImportJob, listJobAnomalies, submitAnomalyDecision, getImportReport } from '../api/imports';
import type { ImportAnomaly } from '../api/imports';
import { getGroup } from '../api/groups';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { Badge } from '../components/ui/Badge';
import { 
  ArrowLeft, CheckCircle2, XCircle, HelpCircle as QuestionIcon, AlertCircle 
} from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const decisionSchema = z.object({
  decision: z.enum(['approve', 'reject', 'ignore']),
  decision_reason: z.string().min(1, 'Please provide a reason/explanation for the audit logs'),
});

type DecisionFormValues = z.infer<typeof decisionSchema>;

export const ImportDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);
  const queryClient = useQueryClient();

  const [reviewingAnomaly, setReviewingAnomaly] = useState<ImportAnomaly | null>(null);

  // Queries
  const { data: job, isLoading: jobLoading } = useQuery({
    queryKey: ['import-job', jobId],
    queryFn: () => getImportJob(jobId),
  });

  const { data: anomalies, isLoading: anomaliesLoading } = useQuery({
    queryKey: ['anomalies', jobId],
    queryFn: () => listJobAnomalies(jobId),
  });

  const { data: group } = useQuery({
    queryKey: ['group', job?.group],
    queryFn: () => getGroup(job!.group),
    enabled: !!job?.group,
  });

  const { data: report } = useQuery({
    queryKey: ['report', jobId],
    queryFn: () => getImportReport(jobId),
    enabled: job?.status === 'completed' || job?.status === 'review_required',
  });

  // Decision Mutation
  const decisionMutation = useMutation({
    mutationFn: (input: { anomalyId: number, decision: 'approve' | 'reject' | 'ignore', reason: string }) => 
      submitAnomalyDecision(input.anomalyId, input.decision, input.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies', jobId] });
      queryClient.invalidateQueries({ queryKey: ['import-job', jobId] });
      queryClient.invalidateQueries({ queryKey: ['report', jobId] });
      queryClient.invalidateQueries({ queryKey: ['balances'] });
      setReviewingAnomaly(null);
      reset();
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to submit decision.');
    }
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DecisionFormValues>({
    resolver: zodResolver(decisionSchema),
  });

  const onDecisionSubmit = (data: DecisionFormValues) => {
    if (reviewingAnomaly) {
      decisionMutation.mutate({
        anomalyId: reviewingAnomaly.id,
        decision: data.decision,
        reason: data.decision_reason,
      });
    }
  };

  const getSeverityColor = (severity: ImportAnomaly['severity']) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-red-50 text-red-700 border-red-100';
      case 'medium': return 'bg-amber-50 text-amber-700 border-amber-100';
      case 'low': return 'bg-blue-50 text-blue-700 border-blue-100';
      default: return 'bg-slate-50 text-slate-700 border-slate-100';
    }
  };

  if (jobLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] space-y-2">
        <AlertCircle className="h-8 w-8 text-slate-400" />
        <p className="text-sm text-slate-500 font-semibold">Import Job not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-slate-200 pb-5">
        <Link 
          to="/imports"
          className="inline-flex items-center text-slate-500 hover:text-slate-900 text-xs font-semibold gap-1.5 mb-4 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Ingestion Portal
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{job.original_filename}</h1>
            <p className="text-sm text-slate-500 font-medium mt-1">Uploaded to {group?.name || 'Group'}</p>
          </div>
          <Badge variant={job.status === 'completed' ? 'success' : job.status === 'review_required' ? 'warning' : 'info'}>
            Status: {job.status.replace('_', ' ')}
          </Badge>
        </div>
      </div>

      {/* Report Summary Cards (if finished or in review) */}
      {report && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="text-center">
            <CardContent className="pt-4 pb-4">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Total Rows</span>
              <span className="text-xl font-extrabold text-slate-900 mt-1 block">{report.total_rows}</span>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4 pb-4">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Imported</span>
              <span className="text-xl font-extrabold text-green-600 mt-1 block">{report.imported_rows}</span>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4 pb-4">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Skipped</span>
              <span className="text-xl font-extrabold text-amber-500 mt-1 block">{report.skipped_rows}</span>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4 pb-4">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Failed</span>
              <span className="text-xl font-extrabold text-red-600 mt-1 block">{report.failed_rows}</span>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4 pb-4">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Anomalies</span>
              <span className="text-xl font-extrabold text-slate-900 mt-1 block">{report.anomaly_count}</span>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Anomalies review / breakdown grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Anomalies List */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Flagged Anomalies Review Queue</CardTitle>
          </CardHeader>
          <CardContent>
            {anomaliesLoading ? (
              <div className="h-20 flex items-center justify-center text-slate-400 text-sm">Loading anomalies log...</div>
            ) : !anomalies || anomalies.length === 0 ? (
              <div className="h-20 flex items-center justify-center text-slate-400 text-sm">No anomalies detected in this job. All rows valid.</div>
            ) : (
              <div className="space-y-4">
                {anomalies.map((anom) => (
                  <div 
                    key={anom.id}
                    className="border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase">Row {anom.import_row}</span>
                        <Badge className={`text-[10px] px-2 py-0.5 rounded-full border ${getSeverityColor(anom.severity)}`}>
                          {anom.severity}
                        </Badge>
                        <Badge variant="default" className="text-[10px]">
                          Category: {anom.anomaly_category}
                        </Badge>
                      </div>
                      <p className="text-sm font-semibold text-slate-900">{anom.description}</p>
                      <div className="text-[10px] text-slate-500 font-medium">Policy suggestion: <code className="bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded font-mono">{anom.detected_action}</code></div>
                    </div>
                    
                    <div className="shrink-0 flex items-center gap-2">
                      {anom.user_decision ? (
                        <div className="flex items-center gap-1.5 text-xs font-semibold">
                          {anom.user_decision === 'approve' ? (
                            <Badge variant="success" className="gap-1"><CheckCircle2 className="h-3 w-3" /> Approved</Badge>
                          ) : anom.user_decision === 'reject' ? (
                            <Badge variant="error" className="gap-1"><XCircle className="h-3 w-3" /> Rejected</Badge>
                          ) : (
                            <Badge variant="default" className="gap-1"><QuestionIcon className="h-3 w-3" /> Ignored</Badge>
                          )}
                        </div>
                      ) : (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => setReviewingAnomaly(anom)}
                          className="text-xs py-1"
                        >
                          Resolve
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Report Breakdown Graph / List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Anomaly Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {!report || !report.report_json?.anomaly_breakdown || Object.keys(report.report_json.anomaly_breakdown).length === 0 ? (
              <div className="h-20 flex items-center justify-center text-slate-400 text-sm">No anomaly metrics compiled</div>
            ) : (
              <div className="space-y-4">
                {Object.entries(report.report_json.anomaly_breakdown).map(([category, count]) => (
                  <div key={category} className="space-y-1 text-sm font-semibold">
                    <div className="flex justify-between text-slate-700">
                      <span className="capitalize">{category}</span>
                      <span>{count}</span>
                    </div>
                    {/* Visual Progress bar */}
                    <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                      <div 
                        className="bg-violet-600 h-full rounded-full" 
                        style={{ width: `${(count / report.anomaly_count) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* SUBMIT DECISION MODAL */}
      <Dialog
        isOpen={reviewingAnomaly !== null}
        onClose={() => setReviewingAnomaly(null)}
        title="Resolve Row Anomaly"
      >
        <form onSubmit={handleSubmit(onDecisionSubmit)} className="space-y-4">
          <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 text-xs font-semibold text-slate-700 space-y-1.5">
            <div><span className="text-slate-400 uppercase font-bold mr-1">Anomaly ID:</span> {reviewingAnomaly?.anomaly_type}</div>
            <div><span className="text-slate-400 uppercase font-bold mr-1">Category:</span> {reviewingAnomaly?.anomaly_category}</div>
            <div><span className="text-slate-400 uppercase font-bold mr-1">Description:</span> {reviewingAnomaly?.description}</div>
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">Review Decision</label>
            <select
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none"
              {...register('decision')}
            >
              <option value="approve">Approve (process/ingest this row)</option>
              <option value="reject">Reject (skip and do not import)</option>
              <option value="ignore">Ignore (park under warning, no action)</option>
            </select>
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-slate-600 tracking-wide">Decision Reason</label>
            <textarea
              placeholder="e.g. Verified paper receipt, duplicate is actually a separate split cost"
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none min-h-[80px]"
              {...register('decision_reason')}
            />
            {errors.decision_reason && (
              <span className="text-[11px] text-red-500 font-medium">{errors.decision_reason.message}</span>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button variant="outline" type="button" onClick={() => setReviewingAnomaly(null)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={decisionMutation.isPending}>
              Submit Decision
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
};
export default ImportDetails;
