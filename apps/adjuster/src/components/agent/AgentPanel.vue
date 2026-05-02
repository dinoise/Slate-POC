<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { UseAgentChatReturn } from '@slate/composables'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentCardFeed from './AgentCardFeed.vue'
import AgentInput from './AgentInput.vue'

const props = defineProps<{
  chat: UseAgentChatReturn
  visible: boolean
}>()

const expanded = ref(false)
const feedRef = ref<HTMLElement | null>(null)

// Count unread messages (agent messages added while collapsed)
const lastSeenCount = ref(0)
const unreadCount = computed(() => {
  if (expanded.value) return 0
  const agentMsgs = props.chat.messages.value.filter((m) => m.role === 'agent').length
  return Math.max(0, agentMsgs - lastSeenCount.value)
})

watch(
  () => props.chat.messages.value.length,
  async () => {
    if (expanded.value) {
      await nextTick()
      scrollToBottom()
    }
  },
)

watch(expanded, (val) => {
  if (val) {
    lastSeenCount.value = props.chat.messages.value.filter((m) => m.role === 'agent').length
    nextTick(() => scrollToBottom())
  }
})

// Auto-expand when a new alert card arrives
watch(
  () => props.chat.messages.value,
  (msgs) => {
    const latest = msgs[msgs.length - 1]
    if (latest?.cardType === 'alert' && !expanded.value) {
      expanded.value = true
    }
  },
  { deep: true },
)

function scrollToBottom() {
  if (feedRef.value) {
    feedRef.value.scrollTop = feedRef.value.scrollHeight
  }
}

function toggleExpanded() {
  expanded.value = !expanded.value
}

function dismissMessage(id: string) {
  const idx = props.chat.messages.value.findIndex((m) => m.id === id)
  if (idx !== -1) props.chat.messages.value.splice(idx, 1)
}

// Touch/swipe gesture handling
const touchStartY = ref(0)
function onTouchStart(e: TouchEvent) {
  touchStartY.value = e.touches[0]?.clientY ?? 0
}
function onTouchEnd(e: TouchEvent) {
  const dy = (e.changedTouches[0]?.clientY ?? 0) - touchStartY.value
  if (dy < -40) expanded.value = true   // swipe up
  if (dy > 40)  expanded.value = false  // swipe down
}
</script>

<template>
  <Transition name="panel-slide">
    <div
      v-if="visible"
      class="agent-panel"
      :class="{ 'agent-panel--expanded': expanded }"
      @touchstart.passive="onTouchStart"
      @touchend.passive="onTouchEnd"
    >
      <!-- Drag handle -->
      <div class="agent-panel__handle" @click="toggleExpanded">
        <div class="handle-bar" />
      </div>

      <!-- Status bar — always visible -->
      <AgentStatusBar
        :is-streaming="chat.isStreaming.value"
        :is-loading="chat.isLoading.value"
        :has-session="chat.hasSession.value"
        :unread-count="unreadCount"
        @click="toggleExpanded"
      />

      <!-- Expandable body -->
      <Transition name="body-expand">
        <div v-if="expanded" class="agent-panel__body">
          <div ref="feedRef" class="agent-panel__feed">
            <AgentCardFeed
              :messages="chat.messages.value"
              @dismiss="dismissMessage"
            />
          </div>

          <AgentInput
            :disabled="chat.isStreaming.value || !chat.hasSession.value"
            @send="chat.sendMessage"
          />
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.agent-panel {
  position: fixed;
  bottom: 0;
  /* Mobile: full width */
  left: 0;
  right: 0;
  /* Above Leaflet (uses z-index 400 internally) */
  z-index: 500;
  background: rgb(var(--v-theme-surface));
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  /* Collapsed height — handle (20px) + status bar (48px) */
  max-height: 68px;
  /* Animate expansion via max-height transition */
  transition: max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  /* Respect iOS safe area at bottom */
  padding-bottom: env(safe-area-inset-bottom);
}

.agent-panel--expanded {
  max-height: 62dvh;
}

/* Desktop: anchor only over the map area (sidebar is 320px wide) */
@media (min-width: 768px) {
  .agent-panel {
    left: 320px;
    border-radius: 12px 12px 0 0;
  }
}

.agent-panel__handle {
  display: flex;
  justify-content: center;
  padding: 8px 0 2px;
  cursor: pointer;
  touch-action: none;
  flex-shrink: 0;
}

.handle-bar {
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: rgba(128, 128, 128, 0.4);
}

.agent-panel__body {
  display: flex;
  flex-direction: column;
  /* Fill the space between status bar and bottom */
  height: calc(62dvh - 68px);
  overflow: hidden;
}

.agent-panel__feed {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

/* Slide up from bottom */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateY(100%);
}

/* Body fade */
.body-expand-enter-active,
.body-expand-leave-active {
  transition: opacity 0.15s ease;
}
.body-expand-enter-from,
.body-expand-leave-to {
  opacity: 0;
}
</style>
