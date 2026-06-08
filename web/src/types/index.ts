export interface Overview {
  wiki_pages: number; concepts: number; memories: number;
  eval_avg: number; eval_count: number; todos_total: number; todos_pending: number;
}

export interface EvalTrend { date: string; avg: number; count: number }
export interface WikiGrowth { date: string; pages: number }

export interface TodoStats {
  total: number; pending: number; done: number; cancelled: number; overdue: number;
  recent: { title: string; status: string; priority: string; deadline: string; created: string }[];
}

export interface MemoryDist { labels: string[]; counts: number[] }

export interface GapItem { topic: string; count: number }
export interface ReminderItem { content: string; trigger: string }

export interface SkillItem { name: string; description: string; tier: number; model: string; triggers: string[]; count: number }
export interface WikiDir { directory: string; count: number; pages: { title: string; type: string; tags: string[]; updated: string }[] }
export interface LogItem { type: string; icon: string; summary: string; score: number | null; created: string }

export interface ServiceStatus { [key: string]: boolean }
export interface GpuInfo { name: string; util: string; mem_used: string; mem_total: string; temp: string }
export interface SystemInfo { uptime: string; mem_used: string; mem_total: string; disk_used: string; disk_total: string; disk_pct: string }

export interface ServerStatus { services: ServiceStatus; gpu: GpuInfo; system: SystemInfo }

export interface DashboardData {
  overview: Overview; eval_trend: EvalTrend[]; wiki_growth: WikiGrowth[];
  todos: TodoStats; memory_dist: MemoryDist; gaps: GapItem[]; reminders: ReminderItem[];
  skills: SkillItem[]; wiki_pages: WikiDir[]; query_log: LogItem[]; server_status: ServerStatus;
}

export interface ConvItem { id: string; title: string; updated_at: string }
export interface ConvMsg { role: 'user' | 'bot'; text: string; time: string }
export interface ConvDetail { id: string; title: string; messages: ConvMsg[] }
