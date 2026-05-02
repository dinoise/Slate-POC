<script setup lang="ts">
import { ref, computed } from 'vue'

// Cross-browser SpeechRecognition — webkit prefix on Chrome/Android
type AnySpeechRecognition = typeof window extends { SpeechRecognition: infer T } ? T : never
interface SpeechRecognitionInstance {
  lang: string
  interimResults: boolean
  maxAlternatives: number
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start(): void
  stop(): void
}
type SpeechRecognitionCtor = new () => SpeechRecognitionInstance
type ExtendedWindow = Window & typeof globalThis & {
  SpeechRecognition?: SpeechRecognitionCtor
  webkitSpeechRecognition?: SpeechRecognitionCtor
}

const props = defineProps<{
  disabled: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const text = ref('')
const isListening = ref(false)
let recognition: SpeechRecognitionInstance | null = null

const canSend = computed(() => text.value.trim().length > 0 && !props.disabled)
const supportsSpeech = typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

function send() {
  const msg = text.value.trim()
  if (!msg || props.disabled) return
  emit('send', msg)
  text.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function toggleVoice() {
  if (!supportsSpeech) return

  if (isListening.value) {
    recognition?.stop()
    return
  }

  const w = window as ExtendedWindow
  const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition
  if (!SR) return
  recognition = new SR()
  recognition.lang = 'es-MX'
  recognition.interimResults = false
  recognition.maxAlternatives = 1

  recognition.onresult = (event: SpeechRecognitionEvent) => {
    const transcript = event.results[0]?.[0]?.transcript ?? ''
    if (transcript) {
      text.value = transcript
      send()
    }
  }
  recognition.onend = () => { isListening.value = false }
  recognition.onerror = () => { isListening.value = false }

  recognition.start()
  isListening.value = true
}
</script>

<template>
  <div class="agent-input pa-3 pt-2">
    <v-divider class="mb-2" />
    <div class="d-flex align-end gap-2">
      <v-textarea
        v-model="text"
        placeholder="Pregunta al asistente..."
        variant="outlined"
        density="compact"
        rows="1"
        auto-grow
        max-rows="4"
        hide-details
        :disabled="disabled"
        class="flex-grow-1"
        @keydown="onKeydown"
      />
      <v-btn
        v-if="supportsSpeech"
        :icon="isListening ? 'mdi-microphone-off' : 'mdi-microphone'"
        :color="isListening ? 'error' : 'grey'"
        variant="text"
        size="large"
        :disabled="disabled"
        @click="toggleVoice"
      />
      <v-btn
        icon="mdi-send"
        color="primary"
        variant="flat"
        size="large"
        :disabled="!canSend"
        @click="send"
      />
    </div>
  </div>
</template>

<style scoped>
.agent-input {
  flex-shrink: 0;
}
</style>
