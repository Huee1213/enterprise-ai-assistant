import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useHealthStore = defineStore('health', () => {
  const data = ref<any>(null)
  const loaded = ref(false)
  const isFetching = ref(false)
  const refreshSeconds = ref(30)
  let timer: ReturnType<typeof setTimeout> | null = null

  let fetching = false

  async function fetchHealth() {
    if (fetching) return
    fetching = true
    isFetching.value = true
    try {
      const resp = await window.fetch('/health')
      if (resp.ok) {
        data.value = await resp.json()
      }
    } catch {
      // ignore
    } finally {
      loaded.value = true
      isFetching.value = false
      fetching = false
      if (timer !== null) {
        timer = setTimeout(fetchHealth, refreshSeconds.value * 1000)
      }
    }
  }

  function startAutoRefresh(seconds?: number) {
    if (seconds !== undefined) refreshSeconds.value = seconds
    stopAutoRefresh()
    timer = setTimeout(fetchHealth, 0)
  }

  function stopAutoRefresh() {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function setRefreshSeconds(seconds: number) {
    refreshSeconds.value = seconds
    if (timer !== null) {
      stopAutoRefresh()
      timer = setTimeout(fetchHealth, 0)
    }
  }

  return {
    data,
    loaded,
    isFetching,
    refreshSeconds,
    fetch: fetchHealth,
    startAutoRefresh,
    stopAutoRefresh,
    setRefreshSeconds,
  }
})
