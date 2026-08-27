import React, { useState, useEffect } from 'react';
import { Plus, Search, Filter, MoreVertical, Play, Pause, Trash2, Clock, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import type { Task } from '../../types';
import { format, formatDistanceToNow } from 'date-fns';

export function TasksPage() {
  const { tasks, loading, error, loadTasks, createTask, getTask } = useApi();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTaskInput, setNewTaskInput] = useState('');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState<'all' | 'running' | 'completed' | 'failed'>('all');

  const filteredTasks = tasks.filter(t => {
    if (filter === 'all') return true;
    return t.status === filter;
  });

  const handleCreateTask = async () => {
    if (!newTaskInput.trim()) return;
    try {
      await createTask(newTaskInput);
      setNewTaskInput('');
      setShowCreateModal(false);
    } catch (e) {
      console.error('Failed to create task:', e);
    }
  };

  const handleTaskClick = async (task: Task) => {
    if (task.status === 'running') {
      setSelectedTask(task);
    } else {
      try {
        const fullTask = await getTask(task.id);
        setSelectedTask(fullTask);
      } catch (e) {
        console.error('Failed to load task:', e);
      }
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return <span className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded">Running</span>;
      case 'completed':
        return <span className="px-2 py-0.5 text-xs bg-success/10 text-success rounded">Completed</span>;
      case 'failed':
        return <span className="px-2 py-0.5 text-xs bg-danger/10 text-danger rounded">Failed</span>;
      case 'planning':
        return <span className="px-2 py-0.5 text-xs bg-warning/10 text-warning rounded">Planning</span>;
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
          <h1 className="text-2xl font-bold">Tasks</h1>
          <p className="text-muted text-sm">Manage and monitor task execution</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover transition"
        >
          <Plus className="w-4 h-4" />
          New Task
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="search"
            placeholder="Search tasks..."
            className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          />
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'running', 'completed', 'failed'] as const).map(f => (
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

      {/* Task List */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64 text-danger">
            <AlertTriangle className="w-6 h-6 mr-2" />
            Failed to load tasks: {error}
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <Clock className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg">No tasks found</p>
            <p className="text-sm">Create your first task to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredTasks.map(task => (
              <button
                key={task.id}
                onClick={() => handleTaskClick(task)}
                className="w-full p-4 hover:bg-background transition text-left flex items-center justify-between gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium truncate">{task.objective}</h3>
                    {getStatusBadge(task.status)}
                    {getRiskBadge(task.steps[0]?.risk_level || 'low')}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
                    </span>
                    {task.completed_at && (
                      <span className="flex items-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" />
                        {formatDistanceToNow(new Date(task.completed_at), { addSuffix: true })}
                      </span>
                    )}
                    <span>{task.steps.filter(s => s.verified).length}/{task.steps.length} steps</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {task.status === 'running' && (
                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">New Task</h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <textarea
              value={newTaskInput}
              onChange={e => setNewTaskInput(e.target.value)}
              placeholder="What would you like Deezy to do?"
              className="w-full min-h-[100px] px-4 py-3 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light resize-none mb-4"
              rows={4}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTask}
                disabled={!newTaskInput.trim()}
                className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50"
              >
                Create Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task Detail Panel */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h2 className="font-semibold">Task Details</h2>
              <button onClick={() => setSelectedTask(null)} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <h3 className="font-medium mb-2">{selectedTask.objective}</h3>
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
                {selectedTask.completed_at && (
                  <div>
                    <span className="text-muted block">Completed</span>
                    <span className="font-medium">{format(new Date(selectedTask.completed_at), 'PPp')}</span>
                  </div>
                )}
              </div>
              <div>
                <h4 className="font-medium mb-3">Steps ({selectedTask.steps.filter(s => s.verified).length}/{selectedTask.steps.length})</h4>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {selectedTask.steps.map((step, index) => (
                    <div key={step.step_id} className="flex items-start gap-3 p-3 bg-background rounded-lg">
                      <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-primary/10 text-primary">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{step.description}</p>
                        <p className="text-xs text-muted">{step.tool}</p>
                        {step.error && <p className="text-xs text-danger mt-1">{step.error}</p>}
                        {step.result && step.status === 'completed' && (
                          <details className="mt-1">
                            <summary className="text-xs text-muted cursor-pointer">View result</summary>
                            <pre className="mt-1 text-xs bg-surface border border-border p-2 rounded overflow-auto max-h-32">
                              {JSON.stringify(step.result, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    })}
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
        </div>
      )}
    </div>
  );
}