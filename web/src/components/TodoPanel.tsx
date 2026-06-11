import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import type { TodoItem } from '../types';

export default function TodoPanel() {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [filter, setFilter] = useState<'pending' | 'done' | 'cancelled' | 'all'>('pending');
  const [newTitle, setNewTitle] = useState('');
  const [newPriority, setNewPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTodos = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await api.listTodos(filter === 'all' ? undefined : filter);
      setTodos(data.todos);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { fetchTodos(); }, [fetchTodos]);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    try {
      await api.createTodo({ title: newTitle.trim(), priority: newPriority });
      setNewTitle(''); fetchTodos();
    } catch (e: any) { setError(e.message); }
  };

  const handleToggle = async (todo: TodoItem) => {
    const newStatus = todo.status === 'done' ? 'pending' : 'done';
    try {
      await api.updateTodo(todo.id, { status: newStatus });
      fetchTodos();
    } catch (e: any) { setError(e.message); }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteTodo(id);
      fetchTodos();
    } catch (e: any) { setError(e.message); }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleCreate();
  };

  const filters = [
    { key: 'pending' as const, label: '待办' },
    { key: 'done' as const, label: '已完成' },
    { key: 'cancelled' as const, label: '已取消' },
    { key: 'all' as const, label: '全部' },
  ];

  return (
    <div>
      <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-4">待办管理</h3>

      {/* 创建表单 */}
      <div className="flex gap-2 mb-4">
        <input
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="新待办..."
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 placeholder:text-gray-400 focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/10 transition-all"
        />
        <select
          value={newPriority}
          onChange={e => setNewPriority(e.target.value as any)}
          className="border border-gray-200 rounded-lg px-2 py-2 text-sm bg-white text-gray-700"
        >
          <option value="high">高</option>
          <option value="medium">中</option>
          <option value="low">低</option>
        </select>
        <button
          onClick={handleCreate}
          className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-dark transition-colors"
        >
          添加
        </button>
      </div>

      {/* 筛选标签 */}
      <div className="flex gap-1 mb-4">
        {filters.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              filter === f.key
                ? 'bg-accent text-white'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* 列表 */}
      {loading && <p className="text-center py-8 text-gray-400 text-sm">加载中...</p>}
      {error && (
        <div className="flex flex-col items-center py-8 gap-2">
          <p className="text-red-500 text-sm">{error}</p>
          <button onClick={fetchTodos} className="text-sm text-accent hover:underline">重试</button>
        </div>
      )}
      {!loading && !error && todos.length === 0 && (
        <p className="text-center py-8 text-gray-400 text-sm">暂无待办</p>
      )}
      {!loading && !error && todos.map(t => (
        <div key={t.id} className="flex items-center gap-3 py-2.5 border-b border-gray-100 group">
          <input
            type="checkbox"
            checked={t.status === 'done'}
            onChange={() => handleToggle(t)}
            className="w-4 h-4 rounded border-gray-300 text-accent cursor-pointer accent-accent"
          />
          <div className="flex-1 min-w-0">
            <span className={`text-sm ${
              t.status === 'done' ? 'line-through text-gray-400' :
              t.status === 'cancelled' ? 'line-through text-gray-300' :
              'text-gray-700'
            }`}>
              {t.title}
            </span>
            <div className="flex gap-2 mt-0.5">
              <span className={`text-[10px] px-1.5 rounded ${
                t.priority === 'high' ? 'bg-red-50 text-red-600' :
                t.priority === 'low' ? 'bg-emerald-50 text-emerald-600' :
                'bg-amber-50 text-amber-600'
              }`}>
                {t.priority}
              </span>
              {t.deadline && <span className="text-[10px] text-gray-400">⏰ {t.deadline?.slice(0, 10)}</span>}
              <span className="text-[10px] text-gray-400">{t.created_at?.slice(0, 10)}</span>
            </div>
          </div>
          <button
            onClick={() => handleDelete(t.id)}
            className="text-gray-300 hover:text-red-500 text-sm opacity-0 group-hover:opacity-100 transition-opacity"
            title="删除"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
