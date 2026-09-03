<script setup lang="ts">
import { onBeforeMount } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
onBeforeMount(() => {
  void router.replace('/user/dashboard');
});
</script>

<template>
  <div />
</template>
