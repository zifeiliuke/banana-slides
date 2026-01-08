import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import * as api from '@/api/endpoints';
import { createBackoff } from '@/utils/polling';

// Note: Backend uses 'RUNNING' but we also accept 'PROCESSING' for compatibility
export type ExportTaskStatus = 'PENDING' | 'PROCESSING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type ExportTaskType = 'pptx' | 'pdf' | 'editable-pptx';

export interface ExportTask {
  id: string;
  taskId: string;
  projectId: string;
  type: ExportTaskType;
  status: ExportTaskStatus;
  pageIds?: string[]; // 选中的页面ID列表，undefined表示全部
  progress?: {
    total: number;
    completed: number;
    percent?: number;
    current_step?: string;
    messages?: string[];
    queue_status?: string;
    queue_name?: string | null;
    queue_length?: number;
    queue_position?: number | null;
    warnings?: string[];  // 导出警告信息
    warning_details?: {   // 警告详细信息
      style_extraction_failed?: Array<{ element_id: string; reason: string }>;
      text_render_failed?: Array<{ text: string; reason: string }>;
      image_add_failed?: Array<{ path: string; reason: string }>;
      json_parse_failed?: Array<{ context: string; reason: string }>;
      other_warnings?: string[];
      total_warnings?: number;
    };
    [key: string]: any;
  };
  downloadUrl?: string;
  filename?: string;
  errorMessage?: string;
  createdAt: string;
  completedAt?: string;
}

interface ExportTasksState {
  tasks: ExportTask[];
  
  // Actions
  addTask: (task: Omit<ExportTask, 'createdAt'>) => void;
  updateTask: (id: string, updates: Partial<ExportTask>) => void;
  removeTask: (id: string) => void;
  clearCompleted: () => void;
  pollTask: (id: string, projectId: string, taskId: string) => Promise<void>;
  restoreActiveTasks: () => void; // 恢复正在进行的任务并重新开始轮询
}

export const useExportTasksStore = create<ExportTasksState>()(
  persist(
    (set, get) => ({
      tasks: [],

      addTask: (task) => {
        set((state) => {
          // Check if task with this id already exists
          const existingIndex = state.tasks.findIndex(t => t.id === task.id);
          
          if (existingIndex >= 0) {
            // Update existing task
            const updatedTasks = [...state.tasks];
            updatedTasks[existingIndex] = {
              ...updatedTasks[existingIndex],
              ...task,
              // Update completedAt if status changed to completed/failed
              completedAt: (task.status === 'COMPLETED' || task.status === 'FAILED')
                ? new Date().toISOString()
                : updatedTasks[existingIndex].completedAt,
            };
            return { tasks: updatedTasks };
          } else {
            // Add new task
            const newTask: ExportTask = {
              ...task,
              createdAt: new Date().toISOString(),
            };
            return {
              tasks: [newTask, ...state.tasks].slice(0, 20), // Keep max 20 tasks
            };
          }
        });
      },

      updateTask: (id, updates) => {
        set((state) => ({
          tasks: state.tasks.map((task) =>
            task.id === id ? { ...task, ...updates } : task
          ),
        }));
      },

      removeTask: (id) => {
        set((state) => ({
          tasks: state.tasks.filter((task) => task.id !== id),
        }));
      },

      clearCompleted: () => {
        set((state) => ({
          tasks: state.tasks.filter(
            (task) => task.status !== 'COMPLETED' && task.status !== 'FAILED'
          ),
        }));
      },

      pollTask: async (id, projectId, taskId) => {
        const backoff = createBackoff({ minMs: 1000, maxMs: 8000, factor: 1.5, jitterRatio: 0.2 });
        let lastProgressKey = '';

        const apply = (task: any) => {
          const updates: Partial<ExportTask> = {
            status: task.status as ExportTaskStatus,
          };

          if (task.progress) {
            // Parse progress if it's a string (from database JSON field)
            let progressData: any = task.progress;
            if (typeof progressData === 'string') {
              try {
                progressData = JSON.parse(progressData);
              } catch (e) {
                console.warn('[ExportTasksStore] Failed to parse progress:', e);
              }
            }

            const queue = task.queue;
            if (queue && queue.backend === 'rq') {
              progressData = {
                ...(progressData || {}),
                queue_status: queue.status,
                queue_name: queue.queue,
                queue_length: queue.queue_length,
                queue_position: queue.position,
              };
            }

            updates.progress = progressData;

            // Extract download URL if available
            if (progressData.download_url) {
              updates.downloadUrl = progressData.download_url;
            }
            if (progressData.filename) {
              updates.filename = progressData.filename;
            }
          }

          if (task.status === 'COMPLETED') {
            updates.completedAt = new Date().toISOString();
          } else if (task.status === 'FAILED') {
            updates.errorMessage = task.error_message || task.error || '导出失败';
            updates.completedAt = new Date().toISOString();
          }

          get().updateTask(id, updates);
        };

        const poll = async () => {
          try {
            const response = await api.getTaskStatus(projectId, taskId);
            const task = response.data;

            if (!task) {
              console.warn('[ExportTasksStore] No task data in response');
              return;
            }
            apply(task);

            const progressKey = JSON.stringify({
              status: task.status,
              progress: task.progress,
              queue: (task as any).queue,
            });
            if (progressKey !== lastProgressKey) {
              backoff.reset();
              lastProgressKey = progressKey;
            }

            if (task.status === 'PENDING' || task.status === 'RUNNING' || task.status === 'PROCESSING') {
              setTimeout(poll, backoff.next());
            }
          } catch (error: any) {
            console.error('[ExportTasksStore] Poll error:', error);
            get().updateTask(id, {
              status: 'FAILED',
              errorMessage: error.message || '轮询失败',
              completedAt: new Date().toISOString(),
            });
          }
        };

        const enableSSE = (import.meta as any).env?.VITE_ENABLE_TASK_SSE === 'true';
        const useSSE = enableSSE && typeof window !== 'undefined' && typeof EventSource !== 'undefined';
        if (!useSSE) {
          await poll();
          return;
        }

        await new Promise<void>((resolve) => {
          let es: EventSource | null = null;
          let fallbackUsed = false;

          const stop = () => {
            if (es) {
              es.close();
              es = null;
            }
          };

          const startPolling = () => {
            poll().finally(resolve);
          };

          es = new EventSource(`/api/projects/${projectId}/tasks/${taskId}/events`);
          es.addEventListener('task', (evt: any) => {
            try {
              const task = JSON.parse(evt.data);
              apply(task);
              if (task.status === 'COMPLETED' || task.status === 'FAILED') {
                stop();
                resolve();
              }
            } catch {
              // ignore
            }
          });
          es.onerror = () => {
            if (fallbackUsed) return;
            fallbackUsed = true;
            stop();
            startPolling();
          };
        });
      },

      restoreActiveTasks: () => {
        // 恢复所有正在进行的任务并重新开始轮询
        const state = get();
        const activeTasks = state.tasks.filter(
          task => task.status === 'PENDING' || task.status === 'PROCESSING' || task.status === 'RUNNING'
        );
        
        if (activeTasks.length > 0) {
          console.log(`[ExportTasksStore] 恢复 ${activeTasks.length} 个正在进行的任务`);
          activeTasks.forEach(task => {
            // 重新开始轮询
            state.pollTask(task.id, task.projectId, task.taskId).catch(err => {
              console.error(`[ExportTasksStore] 恢复任务 ${task.id} 失败:`, err);
            });
          });
        }
      },
    }),
    {
      name: 'export-tasks-storage',
      partialize: (state) => ({
        // Persist all tasks (including active ones) so they can be restored after page refresh
        tasks: state.tasks.slice(0, 20), // Keep max 20 tasks
      }),
    }
  )
);
