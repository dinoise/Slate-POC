import type { AgentType, AgentSessionContext, AssignmentNote } from '@slate/types'
import { getAuthToken } from './index'

const baseUrl = () =>
  (import.meta as ImportMeta & { env: { VITE_API_BASE_URL: string } }).env.VITE_API_BASE_URL ?? ''

export const agentsApi = {
  async createSession(agentType: AgentType, context: AgentSessionContext): Promise<string> {
    const res = await fetch(`${baseUrl()}/api/v1/agents/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
      },
      body: JSON.stringify({ agent_type: agentType, context }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to create agent session')
    }
    const data = (await res.json()) as { session_id: string }
    return data.session_id
  },

  /**
   * Send a message and return a ReadableStream of text chunks.
   * Each chunk is a raw SSE line: "data: <text>\n\n" or "data: [DONE]\n\n".
   * Use streamMessage() for the parsed async iterator instead.
   */
  async sendMessageStream(sessionId: string, message: string): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    const res = await fetch(`${baseUrl()}/api/v1/agents/sessions/${sessionId}/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
      },
      body: JSON.stringify({ message }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to stream agent message')
    }
    if (!res.body) throw new Error('No response body for streaming')
    return res.body.getReader()
  },

  /**
   * Higher-level async generator — yields text chunks until [DONE].
   * Usage: for await (const chunk of agentsApi.streamMessage(id, msg)) { ... }
   */
  async *streamMessage(sessionId: string, message: string): AsyncGenerator<string> {
    const reader = await agentsApi.sendMessageStream(sessionId, message)
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') return
        if (payload.startsWith('[ERROR]')) throw new Error(payload.slice(8))
        if (payload) yield payload
      }
    }
  },

  /** Fire-and-forget — does not throw on failure. */
  deleteSession(sessionId: string): void {
    fetch(`${baseUrl()}/api/v1/agents/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: {
        ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
      },
    }).catch(() => {/* intentional fire-and-forget */})
  },

  async getNotes(assignmentId: number): Promise<AssignmentNote[]> {
    const res = await fetch(`${baseUrl()}/api/v1/assignments/${assignmentId}/notes`, {
      headers: {
        ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
      },
    })
    if (!res.ok) return []
    return res.json() as Promise<AssignmentNote[]>
  },
}
