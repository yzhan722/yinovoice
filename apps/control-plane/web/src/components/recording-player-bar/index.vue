<template>
  <Teleport to="body">
    <div v-if="visible && src" class="recording-player-bar">
      <audio ref="audioRef" :src="src" @timeupdate="onTimeUpdate" @loadedmetadata="onLoadedMetadata" @ended="onEnded" />
      <div class="player-inner">
        <div class="player-controls">
          <t-button v-if="!playing" theme="success" variant="text" size="medium" class="btn-icon" @click="play">
            <template #icon><PlayCircleIcon size="26px" /></template>
          </t-button>
          <t-button v-else theme="primary" variant="text" size="medium" class="btn-icon" @click="pause">
            <template #icon><PauseCircleIcon size="26px" /></template>
          </t-button>
          <t-button theme="danger" variant="text" size="medium" class="btn-icon" @click="stop">
            <template #icon><StopCircleIcon size="26px" /></template>
          </t-button>
        </div>
        <div class="player-progress-wrap">
          <input
            ref="progressBarRef"
            type="range"
            class="progress-range"
            :min="0"
            :max="duration && duration > 0 ? duration : 100"
            step="any"
            :disabled="!duration || duration <= 0"
            :value="displayTime"
            @mousedown="userSeeking = true"
            @touchstart.passive="userSeeking = true"
            @input="onRangeInput"
            @change="onRangeChange"
          />
          <span class="time-text">{{ formatTime(displayTime) }} / {{ formatTime(duration) }}</span>
        </div>
        <t-button theme="default" variant="text" size="medium" class="btn-close btn-icon" @click="close">
          <template #icon><CloseIcon size="26px" /></template>
        </t-button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { PlayCircleIcon, PauseCircleIcon, StopCircleIcon, CloseIcon } from 'tdesign-icons-vue-next';

const props = defineProps<{
  visible: boolean;
  src: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void;
  (e: 'close'): void;
}>();

const audioRef = ref<HTMLAudioElement | null>(null);
const progressBarRef = ref<HTMLInputElement | null>(null);
const displayTime = ref(0);
const duration = ref(0);
const playing = ref(false);
const userSeeking = ref(false);
let rafId = 0;
let pendingTime = -1;

function formatTime(sec: number) {
  if (!sec || !Number.isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function play() {
  audioRef.value?.play().then(() => { playing.value = true; }).catch(() => {});
}

function pause() {
  audioRef.value?.pause();
  playing.value = false;
}

function stop() {
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
  }
  displayTime.value = 0;
  playing.value = false;
}

function close() {
  pause();
  stop();
  emit('update:visible', false);
  emit('close');
}

function onTimeUpdate() {
  if (userSeeking.value || !audioRef.value) return;
  pendingTime = audioRef.value.currentTime;
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0;
    if (pendingTime >= 0 && !userSeeking.value) {
      const el = progressBarRef.value;
      if (el) el.value = String(pendingTime);
      displayTime.value = pendingTime;
      pendingTime = -1;
    }
  });
}

function onLoadedMetadata() {
  if (audioRef.value) duration.value = audioRef.value.duration;
}

function onEnded() {
  playing.value = false;
  displayTime.value = 0;
}

function onRangeInput(e: Event) {
  const val = +(e.target as HTMLInputElement).value;
  displayTime.value = val;
  if (audioRef.value) audioRef.value.currentTime = val;
}

function onRangeChange(e: Event) {
  userSeeking.value = false;
  const val = +(e.target as HTMLInputElement).value;
  displayTime.value = val;
  if (audioRef.value) audioRef.value.currentTime = val;
}

function clearSeeking() {
  userSeeking.value = false;
}

onMounted(() => {
  document.addEventListener('mouseup', clearSeeking);
  document.addEventListener('touchend', clearSeeking);
});

onBeforeUnmount(() => {
  document.removeEventListener('mouseup', clearSeeking);
  document.removeEventListener('touchend', clearSeeking);
  if (rafId) cancelAnimationFrame(rafId);
});

watch([() => props.visible, () => props.src], async ([vis, url]) => {
  if (!vis || !url) return;
  duration.value = 0;
  displayTime.value = 0;
  playing.value = false;
  await nextTick();
  const el = audioRef.value;
  if (el) {
    el.load();
    el.play().then(() => { playing.value = true; }).catch(() => {});
  }
});
</script>

<style scoped lang="less">
.recording-player-bar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
  min-width: 400px;
  max-width: 560px;
  padding: 16px 20px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-medium);
  box-shadow: var(--td-shadow-2);
}

.player-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.player-controls {
  display: flex;
  align-items: center;
  gap: 2px;
}

.player-controls :deep(svg),
.btn-close :deep(svg) {
  width: 26px;
  height: 26px;
}

.player-progress-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.progress-range {
  flex: 1;
  min-width: 100px;
  height: 8px;
  margin: 0;
  cursor: pointer;
  accent-color: var(--td-brand-color);
}

.time-text {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  flex-shrink: 0;
}

.btn-close {
  flex-shrink: 0;
}
</style>
