import { ref, computed } from 'vue'
import { agentsApi } from '@slate/api-client'
import type { AgentMessage, AgentCardType, AgentSessionContext, AssignmentNote } from '@slate/types'

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function sessionKey(assignmentId: number): string {
  return `slate_agent_session_${assignmentId}`
}

function inferCardType(content: string, role: 'user' | 'agent'): AgentCardType {
  if (role === 'user') return 'chat'
  const lower = content.toLowerCase()
  if (lower.includes('briefing') || lower.includes('siniestro') || lower.includes('incidente'))
    return 'briefing'
  if (lower.includes('procedimiento') || lower.includes('paso ') || lower.includes('protocolo'))
    return 'procedures'
  if (lower.includes('alerta') || lower.includes('peligro') || lower.includes('emergencia'))
    return 'alert'
  if (lower.includes('nota registrada') || lower.includes('nota guardada'))
    return 'note_logged'
  if (lower.includes('servicio solicitado') || lower.includes('ambulancia') || lower.includes('grúa') || lower.includes('policía'))
    return 'service_requested'
  return 'chat'
}

function noteToMessage(note: AssignmentNote): AgentMessage {
  return {
    id: `note-${note.id}`,
    role: 'agent',
    content: note.content,
    cardType: 'note_logged',
    timestamp: note.created_at,
    isHistorical: true,
  }
}

export function useAgentChat() {
  const sessionId = ref<string | null>(null)
  const messages = ref<AgentMessage[]>([])
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  const hasSession = computed(() => sessionId.value !== null)

  /**
   * Returns true if a NEW session was created, false if an existing one was restored.
   * Callers should only send the proactive auto-message on new sessions.
   */
  async function startSession(context: AgentSessionContext): Promise<boolean> {
    error.value = null
    const stored = localStorage.getItem(sessionKey(context.assignment_id))
    if (stored) {
      sessionId.value = stored
      await _loadHistoricalNotes(context.assignment_id)
      return false
    }

    isLoading.value = true
    try {
      sessionId.value = await agentsApi.createSession('field_guide', context)
      localStorage.setItem(sessionKey(context.assignment_id), sessionId.value)
      await _loadHistoricalNotes(context.assignment_id)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al iniciar sesión con el agente'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function _loadHistoricalNotes(assignmentId: number): Promise<void> {
    try {
      const notes = await agentsApi.getNotes(assignmentId)
      const historical = notes.map(noteToMessage)
      // Prepend historical notes (oldest first, at the top of the feed)
      const existingIds = new Set(messages.value.map((m) => m.id))
      const newNotes = historical.filter((n) => !existingIds.has(n.id))
      if (newNotes.length > 0) {
        messages.value = [...newNotes, ...messages.value]
      }
    } catch {
      // Non-fatal — historical notes are nice to have
    }
  }

  /**
   * Send a message from the user — shown in the feed as a user bubble,
   * then streams the agent response.
   */
  async function sendMessage(text: string): Promise<void> {
    if (!sessionId.value || isStreaming.value) return
    const userMsg: AgentMessage = {
      id: makeId(),
      role: 'user',
      content: text,
      cardType: 'chat',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)
    await _stream(text)
  }

  /**
   * Send an automatic message (e.g. briefing trigger) — NOT shown as a user
   * message in the feed. Only the agent response is rendered as a card.
   */
  async function sendAutoMessage(text: string): Promise<void> {
    if (!sessionId.value || isStreaming.value) return
    await _stream(text)
  }

  async function _stream(text: string): Promise<void> {
    if (!sessionId.value) return
    isStreaming.value = true
    error.value = null

    // Placeholder message that accumulates chunks
    const agentMsg: AgentMessage = {
      id: makeId(),
      role: 'agent',
      content: '',
      cardType: 'chat',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(agentMsg)
    const idx = messages.value.length - 1

    try {
      for await (const rawChunk of agentsApi.streamMessage(sessionId.value, text)) {
        // Backend escapes \n → \\n for SSE transport; restore real newlines
        const chunk = rawChunk.replace(/\\n/g, '\n')
        const current = messages.value[idx]!
        // Use splice for guaranteed Vue reactivity on array element replacement
        messages.value.splice(idx, 1, { ...current, content: current.content + chunk })
      }
      // Infer card type from final accumulated content
      const final = messages.value[idx]!
      messages.value.splice(idx, 1, {
        ...final,
        cardType: inferCardType(final.content, 'agent'),
      })
    } catch (e) {
      const current = messages.value[idx]!
      messages.value.splice(idx, 1, {
        ...current,
        content: 'Error al contactar al asistente. Intenta de nuevo.',
        cardType: 'alert',
      })
      error.value = e instanceof Error ? e.message : 'Error de streaming'
    } finally {
      isStreaming.value = false
    }
  }

  function endSession(assignmentId: number): void {
    if (sessionId.value) {
      agentsApi.deleteSession(sessionId.value) // fire-and-forget
      localStorage.removeItem(sessionKey(assignmentId))
    }
    sessionId.value = null
    messages.value = []
    error.value = null
  }

  function clearMessages(): void {
    messages.value = []
  }

  function dismissMessage(id: string): void {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  return {
    sessionId,
    messages,
    isLoading,
    isStreaming,
    error,
    hasSession,
    startSession,
    sendMessage,
    sendAutoMessage,
    endSession,
    clearMessages,
    dismissMessage,
  }
}

export type UseAgentChatReturn = ReturnType<typeof useAgentChat>
