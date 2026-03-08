/**
 * TypeScript type definitions for Abundance Frontend
 */

export interface Message {
  role: 'user' | 'agent'
  content: string
}

export interface Thread {
  id: string
  messages: Message[]
  created_at: string
}

export interface ResearchPhase {
  id: number
  name: string
  icon: string
  status: 'pending' | 'running' | 'completed'
}

export interface Source {
  title: string
  url: string
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface Job {
  id: string
  status: JobStatus
  result: any
  error: string | null
  created_at: string
  updated_at: string
  process?: any
  controller?: AbortController
}

export interface SSEEvent {
  type: 'job_started' | 'thinking' | 'step_start' | 'step_complete' | 'current_activity' | 'tool_call_start' | 'tool_call_complete' | 'report_stream' | 'agent_message' | 'done' | 'error'
  [key: string]: any
}

export interface SessionData {
  authenticated: boolean
}

export interface HistoryEntry {
  id: string
  query: string
  report: string
  sources: Source[]
  model: string
  createdAt: string
}

export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  'mercury': 'Mercury 2',
  'gemini': 'Gemini 2.5 Flash Lite',
  'deepseek': 'DeepSeek V3.2',
  'glm': 'GLM-4.5-Air',
  'gemini-flash': 'Gemini 2.5 Flash',
}
