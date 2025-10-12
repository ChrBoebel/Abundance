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
}

export interface SSEEvent {
  type: 'job_started' | 'thinking' | 'step_start' | 'step_complete' | 'tool_call_start' | 'tool_call_complete' | 'agent_message' | 'done' | 'error'
  [key: string]: any
}

export interface SessionData {
  authenticated: boolean
}
