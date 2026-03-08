/**
 * localStorage-based history CRUD for research entries.
 */

import type { HistoryEntry } from './types'

const STORAGE_KEY = 'abundance_history'
const MAX_ENTRIES = 50

export function getHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const entries = JSON.parse(raw)
    if (!Array.isArray(entries)) return []
    return entries
  } catch {
    return []
  }
}

export function saveEntry(entry: HistoryEntry): void {
  try {
    const entries = getHistory()
    entries.unshift(entry)
    if (entries.length > MAX_ENTRIES) {
      entries.length = MAX_ENTRIES
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // localStorage full or unavailable — silently fail
  }
}

export function deleteEntry(id: string): void {
  try {
    const entries = getHistory().filter(e => e.id !== id)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // silently fail
  }
}

export function clearHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // silently fail
  }
}
