import React, { useState, useEffect } from 'react';
import { Search, Filter, Download, Clock, CheckCircle, XCircle, AlertTriangle, Loader2, Eye, ChevronRight } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import type { Task } from '../../types';
import { format, formatDistanceToNow } from 'date-fns';

export function HistoryPage() {
  const { tasks, loading, error, loadTasks } = useApi();
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed'>('all');
  const [search, setSearch] = useState('');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const filteredTasks = tasks.filter(t => {
    if (filter !== 'all' && t.status !== filter) return false;
    if (search && !t.objective.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="px-2 py-0.5 text-xs bg-success/10 text-success rounded">Completed</span>;
      case 'failed':
        return <span className="px-2 py-0.5 text-xs bg-danger/10 text-danger rounded">Failed</span>;
      default:
        return <span className="px-2 py-0.5 text-xs bg-secondary/10 text-secondary rounded">{status}</span>;
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'high':
        return <span className="px-2 py-0.5 text-xs bg-danger/10 text-danger rounded">High</span>;
      case 'medium':
        return <span className="px-2 py-0.5 text-xs bg-warning/10 text-warning rounded">Medium</span>;
      default:
        return <span className="px-2 py-0.5 text-xs bg-success/10 text-success rounded">Low</span>;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Task History</h1>
          <p className="text-muted text-sm">View past task executions and results</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search tasks..."
            className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          />
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'completed', 'failed'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-sm rounded-lg transition ${
                filter === f
                  ? 'bg-primary text-white'
                  : 'bg-background hover:bg-secondary/50 text-text-secondary'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* History Table */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64 text-danger">
            <AlertTriangle className="w-6 h-6 mr-2" />
            Failed to load history: {error}
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <Clock className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg">No tasks found</p>
            <p className="text-sm">Tasks will appear here after execution</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-background border-b border-border">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">Task</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider hidden md:table-cell">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider hidden lg:table-cell">Risk</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider hidden lg:table-cell">Duration</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">Steps</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredTasks.map(task => (
                  <tr key={task.id} className="hover:bg-background transition cursor-pointer" onClick={() => setSelectedTask(task)}>
                    <td className="px-4 py-3">
                      {task.objective}</td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      {getStatusBadge(task.status)}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      {getRiskBadge(task.steps[0]?.risk_level || 'low')}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted">
                      {format(new Date(task.created_at), 'MMM d, yyyy HH:mm')}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell text-sm text-muted">
                      {task.completed_at
                        ? formatDistanceToNow(new Date(task.created_at), { addSuffix: true })
                        : 'Running...'}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted">
                      {task.steps.filter(s => s.verified).length}/{task.steps.length}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedTask(task); }}
                        className="p-1.5 hover:bg-background rounded transition text-muted"
                        aria-label="View details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h2 className="font-semibold">Task Details</h2>
              <button onClick={() => setSelectedTask(null)} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="border-b border-border pb-4">
                <h3 className="text-lg font-medium mb-2">{selectedTask.objective}</h3>
                <div className="flex items-center gap-2 flex-wrap">
                  {getStatusBadge(selectedTask.status)}
                  {getRiskBadge(selectedTask.steps[0]?.risk_level || 'low')}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted block">Created</span>
                  <span className="font-medium">{format(new Date(selectedTask.created_at), 'PPp')}</span>
                </div>
                <div>
                  <span className="text-muted block">Status</span>
                  <span className="font-medium capitalize">{selectedTask.status}</span>
                </div>
                {selectedTask.completed_at && (
                  <div>
                    <span className="text-muted block">Completed</span>
                    <span className="font-medium">{format(new Date(selectedTask.completed_at), 'PPp')}</span>
                  </div>
                )}
                <div>
                  <span className="text-muted block">Duration</span>
                  <span className="font-medium">
                    {selectedTask.completed_at
                      ? formatDistanceToNow(new Date(selectedTask.created_at), { addSuffix: true })
                      : 'Running...'}
                  </span>
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-3">Execution Steps ({selectedTask.steps.filter(s => s.verified).length}/{selectedTask.steps.length})</h4>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {selectedTask.steps.map((step, index) => (
                    <div key={step.step_id} className="flex items-start gap-3 p-3 bg-background rounded-lg">
                      <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-primary/10 text-primary">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{step.description}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted">
                          <span className="px-1.5 py-0.5 bg-primary/10 text-primary rounded">{step.tool}</span>
                          <span>{step.status}</span>
                        </div>
                        {step.error && <p className="text-xs text-danger mt-1">{step.error}</p>}
                        {step.result && step.status === 'completed' && (
                          <details className="mt-2">
                            <summary className="text-xs text-muted cursor-pointer">View result</summary>
                            <pre className="mt-1 text-xs bg-surface border border-border p-2 rounded overflow-auto max-h-32 text-text">
                              {JSON.stringify(step.result, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-4 border-t border-border flex justify-end gap-2">
              <button onClick={() => setSelectedTask(null)} className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}