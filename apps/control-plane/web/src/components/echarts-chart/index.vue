<template>
  <div ref="containerRef" class="echarts-chart" :style="{ width, height }" />
</template>

<script setup lang="ts">
import * as echarts from 'echarts';
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';

const props = withDefaults(
  defineProps<{
    option: Record<string, unknown> | null;
    width?: string;
    height?: string;
  }>(),
  {
    option: () => ({}),
    width: '100%',
    height: '100%',
  },
);

const containerRef = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeHandler: (() => void) | null = null;

function initChart() {
  if (!containerRef.value || !props.option) return;
  if (chart) chart.dispose();
  chart = echarts.init(containerRef.value);
  chart.setOption(props.option as any);
  resizeHandler = () => chart?.resize();
  window.addEventListener('resize', resizeHandler);
}

function disposeChart() {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  resizeHandler = null;
  if (chart) {
    chart.dispose();
    chart = null;
  }
}

watch(
  () => props.option,
  (val) => {
    if (chart && val) chart.setOption(val as any, { notMerge: true });
  },
  { deep: true },
);

onMounted(() => {
  initChart();
});

onBeforeUnmount(() => {
  disposeChart();
});
</script>

<style scoped lang="less">
.echarts-chart {
  min-height: 200px;
}
</style>
