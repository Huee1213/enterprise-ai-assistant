<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import apiClient from '@/api/client'
import ConfigTooltip from '@/components/common/ConfigTooltip.vue'

interface ModelItem {
  id: string
  name: string
  dim?: number
  size_gb?: number
  cached?: boolean
  description?: string
}

// Field-level usage descriptions shown via the help icon tooltip.
const FIELD_DESC: Record<string, string> = {
  llm_provider: '选择大语言模型的供应商（OpenAI / DeepSeek / OpenRouter / Anthropic / Ollama / 自定义）。切换后需按对应服务的接入信息填写密钥与地址。',
  llm_api_key: '调用大语言模型的能力 API 密钥。保存后以掩码形式显示，不会回显明文；修改时需重新输入完整密钥。',
  llm_api_base: '模型服务的接口基础地址，需与所选供应商匹配（如 OpenAI 为 https://api.openai.com/v1）。',
  llm_model: '实际用于对话生成与 Agent 推理的模型名称。可点击刷新从供应商拉取当前可用模型列表。',
  llm_temperature: '控制回答随机性（0-2）。值越低回答越稳定保守，适合知识问答；越高越有创意，适合头脑风暴。',
  llm_max_tokens: '单次生成的最大 Token 数上限。过大会增加响应延迟与成本，建议 2048-4096。',
  embedding_provider: '文档向量化所用嵌入模型的服务来源：本地模型（离线、无需密钥）/ OpenAI 兼容 / 与 LLM 供应商一致。切换后需重新索引文档。',
  embedding_api_key: '远程嵌入服务的 API 密钥。本地模式无需填写。',
  embedding_api_base: '远程嵌入服务的接口地址（如 OpenAI https://api.openai.com/v1）。本地模式无需填写。',
  embedding_model: '向量嵌入模型名称，用于将文档分块转为向量。切换后将影响检索效果，需重新索引知识库。',
  embedding_download_provider: '下载本地嵌入模型的 HuggingFace 镜像地址（默认 https://hf-mirror.com）。保存本地配置时系统会自动下载该模型并显示进度，失败则保留原配置。',
  top_k: '检索知识库时返回的文本块数量（1-20）。值越大上下文越丰富但 Token 消耗越高，建议 3-8。',
  score_threshold: '相似度阈值（0-1）。低于该相似度的检索结果将被过滤丢弃。值过低引入噪声、过高遗漏相关信息，建议 0.3-0.5。',
  chunk_size: '文档切块时的每块字符数。过小丢失跨句上下文，过大降低检索精度，建议 500-1000。',
  chunk_overlap: '相邻块之间的重叠字符数，用于保留跨块信息，建议为块大小的 10%-20%。',
  system_prompt: '自定义 AI 助手的系统提示词，设定回复风格与行为边界。留空使用内置默认提示词。',
  enable_web_search: '是否允许 Agent 调用网页搜索工具（通过自托管 SearXNG）获取实时网络信息。',
  enable_knowledge_search: '是否允许 Agent 检索企业知识库文档用于回答。关闭后 AI 无法引用上传的文档。',
  enable_summarize: '是否允许 Agent 对长文本生成摘要。',
  enable_time_tool: '是否允许 Agent 查询当前日期时间（基于服务器时区）。',
  max_tool_rounds: 'Agent 单轮回复中允许的最大工具调用轮次（1-10）。过大可能导致 Agent 陷入循环、响应变慢，建议 3-5。',
}

const config = ref<Record<string, any>>({})
const defaults = ref<Record<string, any>>({})
const loading = ref(true)
const saving = ref(false)
const resetting = ref(false)
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)

// Provider + model fetch (LLM)
const llmProvider = ref('openai')
const llmApiKey = ref('')
const llmApiBase = ref('')
const keyEditing = ref(false)
const keyVisible = ref(false)
const fetchedModels = ref<ModelItem[]>([])
const fetchingModels = ref(false)
const modelDropdownOpen = ref(false)
const modelSearch = ref('')
const prevApiKey = ref('')
const originalKey = ref('')

// Embedding provider
const embProvider = ref('local')
const embApiKey = ref('')
const embApiBase = ref('')
const embKeyEditing = ref(false)
const embKeyVisible = ref(false)
const embFetchedModels = ref<ModelItem[]>([])
const embFetchingModels = ref(false)
const embLocalModels = ref<ModelItem[]>([])
const embFetchingLocal = ref(false)
const embModelOpen = ref(false)
const embModelSearch = ref('')
const embOriginalKey = ref('')

// Track the true env defaults (never overridden) for reset button
const envDefaults = ref<Record<string, any>>({})

// Sync provider refs → config so diffCount detects changes
watch(llmApiKey, (v) => { config.value.llm_api_key = v })
watch(llmApiBase, (v) => { config.value.llm_api_base = v })
watch(llmProvider, (v) => { config.value.llm_provider = v })

// Sync embedding provider refs
watch(embApiKey, (v) => { config.value.embedding_api_key = v })
watch(embApiBase, (v) => { config.value.embedding_api_base = v })
watch(embProvider, (v) => { config.value.embedding_provider = v })

const filteredModels = computed(() => {
  const q = modelSearch.value.toLowerCase().trim()
  if (!q) return fetchedModels.value
  return fetchedModels.value.filter(m => m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q))
})

const filteredEmbModels = computed(() => {
  const q = embModelSearch.value.toLowerCase().trim()
  if (!q) return embFetchedModels.value
  return embFetchedModels.value.filter(m => m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q))
})

// Local-mode models come from the fastembed supported list (offline, authoritative).
const filteredLocalModels = computed(() => {
  const q = embModelSearch.value.toLowerCase().replace(/^local\//, '').trim()
  const list = embLocalModels.value
  if (!q) return list
  return list.filter(m =>
    m.name.toLowerCase().includes(q) || (m.description || '').toLowerCase().includes(q)
  )
})

const canReset = computed(() => {
  for (const k of Object.keys(envDefaults.value)) {
    if (k === 'llm_api_key' || k === 'embedding_api_key') continue
    const v = config.value[k]
    if (k in config.value && v !== envDefaults.value[k]) {
      if (v === '' || v === null || v === undefined) continue
      return true
    }
  }
  return false
})

const llmHasKeyEdit = computed(() =>
  llmApiKey.value && !llmApiKey.value.includes('•')
)
const embHasKeyEdit = computed(() =>
  embApiKey.value && !embApiKey.value.includes('•')
)

// ── Sectioned layout: independent tabs, each saved separately ──────────────
type SectionKey = 'llm' | 'embed' | 'retrieval' | 'agent'
const SECTION_KEYS: Record<SectionKey, string[]> = {
  llm: ['llm_provider', 'llm_api_key', 'llm_api_base', 'llm_model', 'llm_temperature', 'llm_max_tokens'],
  embed: ['embedding_provider', 'embedding_model', 'embedding_api_key', 'embedding_api_base', 'embedding_download_provider'],
  retrieval: ['top_k', 'score_threshold', 'chunk_size', 'chunk_overlap'],
  agent: ['system_prompt', 'enable_web_search', 'enable_knowledge_search', 'enable_summarize', 'enable_time_tool', 'max_tool_rounds'],
}
const SECTION_LABEL: Record<SectionKey, string> = {
  llm: 'LLM 模型',
  embed: '向量嵌入',
  retrieval: '检索参数',
  agent: 'Agent 行为',
}
const activeTab = ref<SectionKey>('llm')

function sectionDiffCount(section: SectionKey): number {
  let n = 0
  for (const k of SECTION_KEYS[section]) {
    if (k === 'llm_api_key' || k === 'embedding_api_key') continue
    const v = config.value[k]
    if (k in config.value && v !== defaults.value[k]) {
      if (v === '' || v === null || v === undefined) continue
      n++
    }
  }
  return n
}

function sectionCanSave(section: SectionKey): boolean {
  if (sectionDiffCount(section) > 0) return true
  if (section === 'llm') return llmHasKeyEdit.value
  if (section === 'embed') return embHasKeyEdit.value
  return false
}

const resettingSection = ref<SectionKey | null>(null)

// Whether this section currently differs from the env defaults.
function sectionCanReset(section: SectionKey): boolean {
  for (const k of SECTION_KEYS[section]) {
    if (k === 'llm_api_key' || k === 'embedding_api_key') continue
    const def = envDefaults.value[k]
    if (def === undefined) continue
    if (config.value[k] !== def) return true
  }
  if (section === 'llm') {
    if (envDefaults.value.llm_provider !== undefined && llmProvider.value !== envDefaults.value.llm_provider) return true
    if (envDefaults.value.llm_api_base !== undefined && llmApiBase.value !== envDefaults.value.llm_api_base) return true
  }
  if (section === 'embed') {
    if (envDefaults.value.embedding_provider !== undefined && embProvider.value !== envDefaults.value.embedding_provider) return true
    if (envDefaults.value.embedding_model !== undefined && config.value.embedding_model !== envDefaults.value.embedding_model) return true
    if (envDefaults.value.embedding_api_base !== undefined && embApiBase.value !== envDefaults.value.embedding_api_base) return true
  }
  return false
}

// Restore a single section's parameters back to the env defaults.
// API keys are preserved (never cleared by a section reset).
async function resetSection(section: SectionKey) {
  if (resettingSection.value) return
  resettingSection.value = section
  const diff: Record<string, any> = {}
  for (const k of SECTION_KEYS[section]) {
    if (k === 'llm_api_key' || k === 'embedding_api_key') continue // keep secrets
    const def = envDefaults.value[k]
    if (def === undefined) continue
    if (config.value[k] !== def) diff[k] = def
  }
  if (section === 'llm') {
    if (envDefaults.value.llm_provider !== undefined) diff.llm_provider = envDefaults.value.llm_provider
    if (envDefaults.value.llm_api_base !== undefined && llmApiBase.value !== envDefaults.value.llm_api_base) diff.llm_api_base = envDefaults.value.llm_api_base
  }
  if (section === 'embed') {
    if (envDefaults.value.embedding_provider !== undefined) diff.embedding_provider = envDefaults.value.embedding_provider
    if (envDefaults.value.embedding_model !== undefined) diff.embedding_model = envDefaults.value.embedding_model
    if (envDefaults.value.embedding_api_base !== undefined && embApiBase.value !== envDefaults.value.embedding_api_base) diff.embedding_api_base = envDefaults.value.embedding_api_base
  }
  try {
    if (Object.keys(diff).length > 0) {
      await apiClient.put('/agent/config', { config: diff })
    }
    toastMsg(`${SECTION_LABEL[section]}已恢复默认`, 'success')
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '恢复失败', 'error')
  } finally {
    resettingSection.value = null
  }
  await reloadConfig()
}

function isModified(key: string): boolean {
  if (key === 'llm_api_key' || key === 'embedding_api_key') return false
  if (!(key in defaults.value)) return false
  const v = config.value[key]
  if (v === '' || v === null || v === undefined) return false
  return config.value[key] !== defaults.value[key]
}

function toastMsg(msg: string, type: 'success' | 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

async function loadConfig() {
  loading.value = true
  try {
    const resp = await apiClient.get('/agent/config')
    config.value = resp.data.config
    envDefaults.value = resp.data.defaults || {}
    llmProvider.value = config.value.llm_provider || 'openai'
    llmApiKey.value = config.value.llm_api_key || ''
    llmApiBase.value = config.value.llm_api_base || ''
    modelSearch.value = config.value.llm_model || ''
    if (llmApiKey.value.includes('••••')) keyEditing.value = false
    else keyEditing.value = !llmApiKey.value
    prevApiKey.value = llmApiKey.value

    embProvider.value = config.value.embedding_provider || 'local'
    // If "same-as-llm", copy current LLM values
    if (embProvider.value === 'same-as-llm') {
      embApiBase.value = llmApiBase.value
      embApiKey.value = llmApiKey.value
    } else {
      embApiKey.value = config.value.embedding_api_key || ''
      embApiBase.value = config.value.embedding_api_base || ''
    }
    embModelSearch.value = String(config.value.embedding_model || '').replace(/^local\//, '')
    if (embApiKey.value.includes('••••')) embKeyEditing.value = false
    else embKeyEditing.value = !embApiKey.value
    embOriginalKey.value = embApiKey.value
  } catch {
    toastMsg('加载配置失败', 'error')
  }
  loading.value = false
  // Use config as baseline for diff tracking
  defaults.value = { ...config.value }
  // Auto-fetch only on initial load if we already have actual credentials
  if (prevApiKey.value && !prevApiKey.value.includes('••••') && llmApiBase.value) fetchModels()
}

async function fetchModels() {
  const keyIsMasked = llmApiKey.value.includes('•')
  if (!keyIsMasked && !llmApiKey.value) {
    toastMsg('请先填写 API Key', 'error')
    return
  }
  if (!llmApiBase.value && !['openai', 'anthropic'].includes(llmProvider.value)) {
    toastMsg('请先填写 API Base URL', 'error')
    return
  }
  const base = llmApiBase.value || (llmProvider.value === 'openai' ? 'https://api.openai.com/v1' : 'https://api.anthropic.com')
  fetchingModels.value = true
  try {
    const resp = await apiClient.post('/agent/config/fetch-models', {
      provider: llmProvider.value,
      api_key: llmApiKey.value.includes('•') ? '' : llmApiKey.value,
      api_base: base,
      type: 'text',
    })
    fetchedModels.value = resp.data.models
    modelDropdownOpen.value = true
    toastMsg(`已获取 ${resp.data.models.length} 个模型`, 'success')
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '获取模型列表失败', 'error')
  }
  fetchingModels.value = false
}

function selectModel(m: ModelItem) {
  config.value.llm_model = m.id
  modelDropdownOpen.value = false
  modelSearch.value = m.name
}

function selectEmbModel(m: ModelItem) {
  config.value.embedding_model = m.id
  embModelOpen.value = false
  embModelSearch.value = m.name
}

async function fetchLocalModels() {
  if (embFetchingLocal.value) return
  embFetchingLocal.value = true
  try {
    const resp = await apiClient.get('/agent/config/embedding/models')
    embLocalModels.value = resp.data.models || []
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '获取本地模型列表失败', 'error')
  }
  embFetchingLocal.value = false
}

function selectLocalModel(m: ModelItem) {
  config.value.embedding_model = m.id // "local/BAAI/bge-small-en-v1.5"
  embModelOpen.value = false
  embModelSearch.value = m.name
}

function handleModelInputFocus() {
  if (fetchedModels.value.length > 0) modelDropdownOpen.value = true
}

function handleModelInputBlur() {
  setTimeout(() => { modelDropdownOpen.value = false }, 200)
  const orig = defaults.value.llm_model
  if (orig !== undefined && (!modelSearch.value.trim() || modelSearch.value === String(orig))) {
    modelSearch.value = String(orig)
    config.value.llm_model = orig
  }
}

function handleEmbModelFocus() {
  if (embProvider.value === 'local') {
    if (embLocalModels.value.length === 0) fetchLocalModels()
    embModelOpen.value = true
  } else if (embFetchedModels.value.length > 0) {
    embModelOpen.value = true
  }
}

function handleEmbModelBlur() {
  setTimeout(() => { embModelOpen.value = false }, 200)
  const orig = defaults.value.embedding_model
  if (orig !== undefined && (!embModelSearch.value.trim() || embModelSearch.value === String(orig))) {
    embModelSearch.value = String(orig)
    config.value.embedding_model = orig
  }
}

function onEmbProviderChange() {
  const p = embProvider.value
  const orig = defaults.value.embedding_provider
  if (p === orig) {
    embProvider.value = orig
    config.value.embedding_provider = orig
    config.value.embedding_api_base = defaults.value.embedding_api_base
    embApiBase.value = defaults.value.embedding_api_base || ''
    config.value.embedding_api_key = defaults.value.embedding_api_key
    return
  }
  if (p === 'same-as-llm') {
    embApiBase.value = llmApiBase.value
    embApiKey.value = llmApiKey.value
    config.value.embedding_api_base = llmApiBase.value
    config.value.embedding_api_key = llmApiKey.value
    // Keep existing embedding model, don't copy from LLM
    config.value.embedding_provider = 'same-as-llm'
    return
  }
  const presets: Record<string, string> = {
    local: '',
    openai: 'https://api.openai.com/v1',
  }
  if (p === 'local') {
    embApiBase.value = ''
    embApiKey.value = ''
    config.value.embedding_api_base = ''
    config.value.embedding_api_key = ''
    if (!config.value.embedding_model || !String(config.value.embedding_model).startsWith('local/')) {
      config.value.embedding_model = 'local/BAAI/bge-small-en-v1.5'
    }
    embModelSearch.value = String(config.value.embedding_model).replace(/^local\//, '')
    fetchLocalModels()
  } else {
    embApiBase.value = presets[p] || ''
    embApiKey.value = ''
  }
  config.value.embedding_provider = p
  config.value.embedding_api_base = embApiBase.value
}

function startEmbKeyEdit() {
  embOriginalKey.value = embApiKey.value
  embKeyEditing.value = true
  embKeyVisible.value = false
}

function onEmbKeyBlur() {
  if (!embApiKey.value.trim() || embApiKey.value === embOriginalKey.value) {
    embApiKey.value = embOriginalKey.value
    embKeyEditing.value = false
    embKeyVisible.value = false
  }
}

async function fetchEmbModels() {
  const p = embProvider.value
  if (p === 'local') {
    toastMsg('本地嵌入模型无需获取', 'success')
    return
  }
  // Resolve "same-as-llm" to the actual provider
  const actualProvider = p === 'same-as-llm' ? llmProvider.value : p
  const keyIsMasked = embApiKey.value.includes('•')
  if (!keyIsMasked && !embApiKey.value) {
    toastMsg('请先填写 Embedding API Key', 'error')
    return
  }
  const base = embApiBase.value || 'https://api.openai.com/v1'
  embFetchingModels.value = true
  try {
    const resp = await apiClient.post('/agent/config/fetch-models', {
      provider: actualProvider,
      api_key: embApiKey.value.includes('•') ? '' : embApiKey.value,
      api_base: base,
      type: 'embedding',
    })
    embFetchedModels.value = resp.data.models
    embModelOpen.value = true
    toastMsg(`已获取 ${resp.data.models.length} 个嵌入模型`, 'success')
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '获取模型列表失败', 'error')
  }
  embFetchingModels.value = false
}

function onProviderChange() {
  const p = llmProvider.value
  const origProvider = defaults.value.llm_provider

  // If selecting the same as default, revert all provider-related fields
  if (p === origProvider) {
    llmProvider.value = origProvider
    config.value.llm_provider = origProvider
    config.value.llm_api_base = defaults.value.llm_api_base
    llmApiBase.value = defaults.value.llm_api_base || ''
    config.value.llm_api_key = defaults.value.llm_api_key
    return
  }

  const presets: Record<string, { base: string; key: string }> = {
    openai: { base: 'https://api.openai.com/v1', key: '' },
    deepseek: { base: 'https://api.deepseek.com/v1', key: '' },
    openrouter: { base: 'https://openrouter.ai/api/v1', key: '' },
    anthropic: { base: 'https://api.anthropic.com', key: '' },
    ollama: { base: 'http://localhost:11434', key: '' },
    custom: { base: '', key: '' },
  }
  const preset = presets[p]
  if (preset) {
    llmApiBase.value = preset.base
    if (preset.key) llmApiKey.value = preset.key
  }
  config.value.llm_provider = p
  config.value.llm_api_base = llmApiBase.value
}

function startKeyEdit() {
  originalKey.value = llmApiKey.value
  keyEditing.value = true
  keyVisible.value = false
}

function onKeyBlur() {
  // If empty or unchanged, revert to original (masked) display
  if (!llmApiKey.value.trim() || llmApiKey.value === originalKey.value) {
    llmApiKey.value = originalKey.value
    keyEditing.value = false
    keyVisible.value = false
  }
}

function revertOnBlur(e: FocusEvent) {
  const el = e.target as HTMLInputElement
  const key = el.dataset.revert
  if (!key) return
  const val = el.value
  const orig = defaults.value[key]
  if (orig !== undefined && (!val.trim() || String(val).trim() === String(orig).trim())) {
    el.value = String(orig)
    config.value[key] = orig
    if (key === 'llm_api_base') llmApiBase.value = orig
    if (key === 'embedding_api_base') embApiBase.value = orig
  }
}

async function reloadConfig() {
  try {
    const resp = await apiClient.get('/agent/config')
    config.value = resp.data.config
    llmProvider.value = config.value.llm_provider || 'openai'
    llmApiKey.value = config.value.llm_api_key || ''
    llmApiBase.value = config.value.llm_api_base || ''
    modelSearch.value = config.value.llm_model || ''
    if (llmApiKey.value.includes('••••')) keyEditing.value = false
    else keyEditing.value = !llmApiKey.value
    prevApiKey.value = llmApiKey.value
    embProvider.value = config.value.embedding_provider || 'local'
    if (embProvider.value === 'same-as-llm') {
      embApiBase.value = llmApiBase.value
      embApiKey.value = llmApiKey.value
    } else {
      embApiKey.value = config.value.embedding_api_key || ''
      embApiBase.value = config.value.embedding_api_base || ''
    }
    embModelSearch.value = String(config.value.embedding_model || '').replace(/^local\//, '')
    if (embApiKey.value.includes('••••')) embKeyEditing.value = false
    else embKeyEditing.value = !embApiKey.value
    embOriginalKey.value = embApiKey.value
  } catch {}
  defaults.value = { ...config.value }
}

// ── Local embedding: download-with-progress + reindex flow ──────────────────
const embeddingBusy = ref(false)
const embeddingProgress = ref<number | null>(null)
const embeddingStageText = ref('')
const embeddingStage = ref<'idle' | 'download' | 'verify' | 'rebuild' | 'indexing'>('idle')

async function consumeEventStream(url: string, body: any, onEvent: (ev: any) => void): Promise<void> {
  const token = localStorage.getItem('token') || ''
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const resp = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!resp.ok) {
    let detail = ''
    try {
      const j = await resp.json()
      detail = j.detail || ''
    } catch { /* ignore */ }
    if (!detail) detail = await resp.text()
    throw new Error((typeof detail === 'string' ? detail : JSON.stringify(detail)).slice(0, 200))
  }
  const reader = resp.body!.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (!line) continue
      const s = line.replace(/^data:\s*/, '')
      if (!s) continue
      try { onEvent(JSON.parse(s)) } catch { /* skip malformed */ }
    }
  }
}

// Build the embedding section diff (same subset as the generic path).
function buildEmbedDiff(): Record<string, any> {
  const diff: Record<string, any> = {}
  const pk = embProvider.value
  if (pk === 'local') {
    // Local mode: model + download provider always explicit.
    const m = (config.value.embedding_model || '').trim()
    const label = m.startsWith('local/') ? m : `local/${m}`
    if (label !== (defaults.value.embedding_model || '')) diff.embedding_model = label
    diff.embedding_provider = 'local'
    const prov = (config.value.embedding_download_provider || '').trim()
    if (prov !== (defaults.value.embedding_download_provider || '')) diff.embedding_download_provider = prov
  } else {
    for (const k of SECTION_KEYS['embed']) {
      if (k === 'embedding_download_provider') continue
      if (k in config.value && config.value[k] !== defaults.value[k]) {
        if (config.value[k] === '' || config.value[k] === null || config.value[k] === undefined) continue
        diff[k] = config.value[k]
      }
    }
    if (embApiKey.value) diff.embedding_api_key = embApiKey.value
    if (embApiBase.value) diff.embedding_api_base = embApiBase.value
    if (pk) diff.embedding_provider = pk
  }
  return diff
}

async function saveEmbedSectionLocal() {
  // Snapshot the previously-saved embedding config so we can revert on failure.
  const prev = {
    embedding_provider: defaults.value.embedding_provider ?? 'local',
    embedding_model: defaults.value.embedding_model || '',
    embedding_download_provider: defaults.value.embedding_download_provider || '',
  }
  const newModel = (config.value.embedding_model || '').trim()
  const label = newModel.startsWith('local/') ? newModel : (newModel ? `local/${newModel}` : '')
  if (!label) { toastMsg('请填写本地嵌入模型名称', 'error'); return }
  const provider = (config.value.embedding_download_provider || '').trim() || 'https://hf-mirror.com'

  const diff = buildEmbedDiff()
  if (Object.keys(diff).length === 0) { toastMsg('该区域没有修改内容', 'success'); return }

  embeddingBusy.value = true
  embeddingStage.value = 'download'
  embeddingStageText.value = '正在准备本地模型…'
  embeddingProgress.value = 0
  saving.value = true

  // 1) Prepare (download with progress) with the NEW model+provider.
  let prepared = false
  try {
    await consumeEventStream('/api/agent/config/embedding/prepare', { model: label, provider }, (ev) => {
      if (ev.stage && ev.stage !== 'downloading') embeddingStageText.value = ev.stage === 'download' ? '正在下载本地嵌入模型…' : ev.stage
      if (typeof ev.progress === 'number') embeddingProgress.value = ev.progress
      if (ev.status === 'ready') prepared = true
      if (ev.status === 'error') {
        prepared = false
        embeddingStageText.value = ev.detail || '模型准备失败'
        throw new Error(ev.detail || '模型准备失败')
      }
    })
  } catch (err: any) {
    embeddingBusy.value = false
    saving.value = false
    embeddingStage.value = 'idle'
    toastMsg(`模型下载失败，已保留原配置：${err.message}`, 'error')
    await reloadConfig()
    return
  }
  if (!prepared) {
    embeddingBusy.value = false
    saving.value = false
    embeddingStage.value = 'idle'
    toastMsg('模型下载失败，已保留原配置', 'error')
    await reloadConfig()
    return
  }

  // 2) Persist the embed config.
  try {
    await apiClient.put('/agent/config', { config: diff })
  } catch (err: any) {
    embeddingBusy.value = false
    saving.value = false
    embeddingStage.value = 'idle'
    toastMsg(err.response?.data?.detail || err.message || '保存失败', 'error')
    await reloadConfig()
    return
  }

  // 3) Apply: rebuild vector store + reindex with progress.
  let applied = false
  try {
    await consumeEventStream('/api/agent/config/embedding/apply', {}, (ev) => {
      if (ev.stage === 'verify') { embeddingStage.value = 'verify'; embeddingStageText.value = ev.message }
      else if (ev.stage === 'rebuild') { embeddingStage.value = 'rebuild'; embeddingStageText.value = ev.message }
      else if (ev.stage === 'indexing') {
        embeddingStage.value = 'indexing'
        embeddingStageText.value = `正在重建知识库索引（${ev.done}/${ev.total}）…`
        if (typeof ev.progress === 'number') embeddingProgress.value = ev.progress
      }
      if (ev.status === 'ok') applied = true
      if (ev.status === 'error') {
        embeddingStageText.value = ev.detail || '索引重建失败'
        throw new Error(ev.detail || '索引重建失败')
      }
    })
  } catch (err: any) {
    // Revert to previously-saved embedding config.
    try {
      await apiClient.put('/agent/config', { config: {
        embedding_provider: prev.embedding_provider,
        embedding_model: prev.embedding_model,
        ...(prev.embedding_download_provider ? { embedding_download_provider: prev.embedding_download_provider } : {}),
      }})
    } catch { /* ignore */ }
    embeddingBusy.value = false
    saving.value = false
    embeddingStage.value = 'idle'
    toastMsg(`索引重建失败，已恢复原配置：${err.message}`, 'error')
    await reloadConfig()
    return
  }

  if (applied) {
    toastMsg('向量嵌入已保存，知识库索引已重建', 'success')
  } else {
    toastMsg('索引重建未完成', 'error')
  }
  embeddingBusy.value = false
  saving.value = false
  embeddingStage.value = 'idle'
  embeddingProgress.value = null
  await reloadConfig()
}

async function saveSection(section: SectionKey) {
  if (section === 'embed' && embProvider.value === 'local') {
    await saveEmbedSectionLocal()
    return
  }
  const diff: Record<string, any> = {}
  for (const k of SECTION_KEYS[section]) {
    if (k in config.value && config.value[k] !== defaults.value[k]) {
      if (config.value[k] === '' || config.value[k] === null || config.value[k] === undefined) continue
      diff[k] = config.value[k]
    }
  }
  // Provider/key/base are driven by local refs; include them for this section.
  if (section === 'llm') {
    if (llmApiKey.value) diff.llm_api_key = llmApiKey.value
    if (llmApiBase.value) diff.llm_api_base = llmApiBase.value
    if (llmProvider.value) diff.llm_provider = llmProvider.value
  }
  if (section === 'embed') {
    if (embApiKey.value) diff.embedding_api_key = embApiKey.value
    if (embApiBase.value) diff.embedding_api_base = embApiBase.value
    if (embProvider.value) diff.embedding_provider = embProvider.value
  }
  if (Object.keys(diff).length === 0) {
    toastMsg('该区域没有修改内容', 'success')
    return
  }
  saving.value = true
  try {
    await apiClient.put('/agent/config', { config: diff })
    toastMsg(`${SECTION_LABEL[section]}已保存`, 'success')
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
  await reloadConfig()
}

async function resetConfig() {
  resetting.value = true
  try {
    const resp = await apiClient.post('/agent/config/reset')
    config.value = resp.data.config
    defaults.value = { ...resp.data.config }
    llmProvider.value = config.value.llm_provider || 'openai'
    llmApiKey.value = config.value.llm_api_key || ''
    llmApiBase.value = config.value.llm_api_base || ''
    modelSearch.value = config.value.llm_model || ''
    fetchedModels.value = []
    keyEditing.value = false
    keyVisible.value = false
    embProvider.value = config.value.embedding_provider || 'local'
    embApiKey.value = config.value.embedding_api_key || ''
    embApiBase.value = config.value.embedding_api_base || ''
    embModelSearch.value = String(config.value.embedding_model || '').replace(/^local\//, '')
    embFetchedModels.value = []
    embKeyEditing.value = false
    embKeyVisible.value = false
    toastMsg('已恢复默认配置', 'success')
  } catch (err: any) {
    toastMsg(err.response?.data?.detail || '重置失败', 'error')
  }
  resetting.value = false
  await reloadConfig()
}

onMounted(loadConfig)
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold">智能体配置</h1>
        <p class="text-sm text-muted-foreground mt-1">
          按分区独立配置、独立保存，保存后即时生效
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button @click="resetConfig" :disabled="resetting || !canReset"
          class="rounded-lg px-3 py-2 text-xs font-medium border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
          title="清空所有配置覆盖，恢复为环境变量默认值">
          <span v-if="resetting" class="inline-flex items-center gap-1.5">
            <svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>重置中...
          </span>
          <span v-else>
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="inline -mt-0.5 mr-1"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            恢复全局默认
          </span>
        </button>
      </div>
    </div>

    <div v-if="toast" class="fixed top-4 right-4 z-50 rounded-lg px-4 py-3 text-sm shadow-lg animate-fade-in"
      :class="toast.type === 'success' ? 'bg-green-500/10 text-green-600 border border-green-500/20' : 'bg-destructive/10 text-destructive border border-destructive/20'">{{ toast.msg }}</div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <svg class="animate-spin text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
    </div>

    <div v-else>
      <!-- Section tabs -->
      <div class="flex items-center gap-1 border-b border-border mb-4 overflow-x-auto">
        <button
          v-for="s in (['llm','embed','retrieval','agent'] as SectionKey[])"
          :key="s"
          @click="activeTab = s"
          class="relative px-4 py-2 text-sm font-medium border-b-2 transition-colors shrink-0"
          :class="activeTab === s ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'"
        >
          {{ SECTION_LABEL[s] }}
          <span v-if="sectionDiffCount(s) > 0" class="ml-1.5 inline-flex items-center rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] px-1.5 py-0.5">{{ sectionDiffCount(s) }}</span>
        </button>
      </div>

      <div class="space-y-4">
        <Transition name="sect-slide" mode="out-in">
          <div :key="activeTab" class="space-y-4">
        <!-- LLM Provider section (custom layout, overflow-visible so dropdown isn't clipped) -->
        <div v-show="activeTab === 'llm'" class="rounded-xl border border-border bg-card overflow-visible">
          <div class="px-5 py-4 border-b border-border/50 bg-muted/20">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold">LLM 模型</h3>
              <p class="text-xs text-muted-foreground mt-0.5">大语言模型连接配置，用于对话生成和 Agent 推理</p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <button @click="resetSection('llm')" :disabled="resettingSection !== null || !sectionCanReset('llm')"
                class="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground border border-border rounded-md px-2 py-1 transition-colors disabled:opacity-40"
                title="恢复本分区为环境变量默认值（不影响其它分区，API Key 保留）">
                <svg v-if="resettingSection === 'llm'" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                恢复默认
              </button>
              <div v-if="['llm_provider','llm_api_key','llm_api_base','llm_model','llm_temperature','llm_max_tokens'].some(k => isModified(k)) || llmHasKeyEdit"
                class="text-[10px] text-amber-500 bg-amber-500/10 rounded-md px-2 py-0.5 font-medium">已修改</div>
            </div>
          </div>
        </div>
        <div class="px-5 py-4 space-y-4">
          <!-- Provider selector -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="服务提供商" :text="FIELD_DESC.llm_provider" /></div>
            <select v-model="llmProvider" @change="onProviderChange"
              class="w-56 h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30">
              <option value="openai">OpenAI</option>
              <option value="deepseek">DeepSeek</option>
              <option value="openrouter">OpenRouter</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama (本地)</option>
              <option value="custom">自定义</option>
            </select>
          </div>

          <!-- API Key -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="API Key" :text="FIELD_DESC.llm_api_key" /></div>
            <div class="w-56 flex items-center gap-1.5">
              <div class="relative flex-1 min-w-0">
                <input
                  v-if="keyEditing"
                  v-model="llmApiKey"
                  :type="keyVisible ? 'text' : 'password'"
                  placeholder="sk-..."
                  @blur="onKeyBlur"
                  class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30 pr-8"
                />
                <div v-else class="h-8 px-3 text-xs text-muted-foreground bg-muted/30 rounded-md border border-border select-none cursor-pointer overflow-hidden leading-8 truncate" @click="startKeyEdit">
                  {{ llmApiKey || '未配置' }}
                </div>
                <!-- Toggle visibility (only in edit mode) -->
                <button
                  v-if="keyEditing"
                  @click="keyVisible = !keyVisible"
                  class="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                  tabindex="-1"
                >
                  <svg v-if="!keyVisible" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                </button>
              </div>
              <button v-if="!keyEditing && llmApiKey && !llmApiKey.includes('未')" @click="startKeyEdit"
                class="shrink-0 text-[10px] text-muted-foreground hover:text-foreground px-1.5 py-1 rounded transition-colors"
                title="修改 API Key">
                修改
              </button>
            </div>
          </div>

          <!-- API Base -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="API Base URL" :text="FIELD_DESC.llm_api_base" /></div>
            <div class="w-56">
              <input v-model="llmApiBase" type="text" placeholder="https://api.openai.com/v1" data-revert="llm_api_base" @blur="revertOnBlur"
                class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
            </div>
          </div>

          <!-- Model name (searchable dropdown + refresh) -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip label="模型名称" :text="FIELD_DESC.llm_model" />
                <span v-if="isModified('llm_model')" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
              <div class="w-56 flex items-center gap-1.5">
              <div class="relative flex-1 min-w-0">
                <input
                  v-model="modelSearch"
                  :title="config.llm_model"
                  @input="config.llm_model = modelSearch; modelDropdownOpen = true"
                  @focus="handleModelInputFocus"
                  @blur="handleModelInputBlur"
                  type="text" placeholder="gpt-4o-mini"
                  class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
                <!-- Dropdown list -->
                <div v-if="modelDropdownOpen && filteredModels.length > 0"
                  class="absolute top-full left-0 right-0 mt-1 z-30 max-h-48 overflow-y-auto rounded-md border border-border bg-popover shadow-lg">
                  <button v-for="m in filteredModels" :key="m.id" @mousedown.prevent="selectModel(m)"
                    class="w-full text-left px-3 py-2 text-xs text-popover-foreground hover:bg-muted transition-colors border-b border-border/30 last:border-0"
                    :class="config.llm_model === m.id ? 'bg-primary/5 font-medium' : ''">
                    <span class="block truncate" :title="m.name">{{ m.name }}</span>
                    <span class="block text-[9px] text-muted-foreground/50 truncate" :title="m.id">{{ m.id }}</span>
                  </button>
                </div>
                <div v-if="modelDropdownOpen && fetchedModels.length > 0 && filteredModels.length === 0"
                  class="absolute top-full left-0 right-0 z-30 mt-1 rounded-md border border-border bg-popover shadow-lg px-3 py-2 text-xs text-muted-foreground/50 text-center">无匹配模型</div>
              </div>
              <button @click="fetchModels" :disabled="fetchingModels"
                class="shrink-0 rounded-md w-8 h-8 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                :title="fetchingModels ? '获取中...' : '刷新模型列表'">
                <svg v-if="fetchingModels" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              </button>
            </div>
          </div>

          <!-- Temperature -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip label="Temperature" :text="FIELD_DESC.llm_temperature" />
                <span v-if="isModified('llm_temperature')" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
            <div class="w-56 flex items-center gap-3">
              <input v-model.number="config.llm_temperature" type="range" min="0" max="2" step="0.05"
                class="flex-1 h-1.5 appearance-none rounded-full bg-muted-foreground/20 accent-primary cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer" />
              <span class="text-xs font-mono text-muted-foreground tabular-nums w-12 text-right">{{ config.llm_temperature }}</span>
            </div>
          </div>

          <!-- Max Tokens -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip label="最大 Token 数" :text="FIELD_DESC.llm_max_tokens" />
                <span v-if="isModified('llm_max_tokens')" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
            <div class="w-56 flex items-center gap-2">
              <input v-model.number="config.llm_max_tokens" type="number" min="256" max="16384" step="256"
                class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground text-center tabular-nums focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <span class="text-[10px] text-muted-foreground">tokens</span>
            </div>
          </div>

          <!-- LLM section save bar -->
          <div class="flex items-center justify-between gap-2 pt-3 border-t border-border/50">
            <span v-if="sectionDiffCount('llm') > 0" class="text-[10px] text-amber-600 dark:text-amber-400">已修改 {{ sectionDiffCount('llm') }} 项</span>
            <span v-else class="text-[10px] text-muted-foreground/50">无修改</span>
            <button @click="saveSection('llm')" :disabled="saving || !sectionCanSave('llm')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
              <svg v-if="saving" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              {{ saving ? '保存中...' : '保存本区' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Embedding -->
      <div v-show="activeTab === 'embed'" class="rounded-xl border border-border bg-card overflow-visible">
        <div class="px-5 py-4 border-b border-border/50 bg-muted/20">
          <div class="flex items-center justify-between">
            <div><h3 class="text-sm font-semibold">向量嵌入</h3><p class="text-xs text-muted-foreground mt-0.5">文档向量化模型配置，用于知识库检索。本地模式无需 API Key</p></div>
            <div class="flex items-center gap-2 shrink-0">
              <button @click="resetSection('embed')" :disabled="resettingSection !== null || !sectionCanReset('embed')"
                class="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground border border-border rounded-md px-2 py-1 transition-colors disabled:opacity-40"
                title="恢复本分区为环境变量默认值（不影响其它分区，API Key 保留）">
                <svg v-if="resettingSection === 'embed'" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                恢复默认
              </button>
              <div v-if="['embedding_provider','embedding_model','embedding_api_key','embedding_api_base'].some(k => isModified(k))"
                class="text-[10px] text-amber-500 bg-amber-500/10 rounded-md px-2 py-0.5 font-medium">已修改</div>
            </div>
          </div>
        </div>
        <div class="px-5 py-4 space-y-4">
          <!-- Embedding provider -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="嵌入供应商" :text="FIELD_DESC.embedding_provider" /></div>
            <select v-model="embProvider" @change="onEmbProviderChange"
              class="w-56 h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30">
              <option value="same-as-llm">与 LLM 供应商一致</option>
              <option value="local">本地模型 (ONNX)</option>
              <option value="openai">OpenAI 兼容</option>
              <option value="custom">自定义</option>
            </select>
          </div>

          <!-- Embedding API Key (only for remote) -->
          <div v-if="embProvider !== 'local'" class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="Embedding API Key" :text="FIELD_DESC.embedding_api_key" /></div>
            <div class="w-56 flex items-center gap-1.5">
              <div class="relative flex-1 min-w-0">
                <input v-if="embKeyEditing" v-model="embApiKey" :type="embKeyVisible ? 'text' : 'password'" placeholder="sk-..." @blur="onEmbKeyBlur"
                  class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30 pr-8" />
                <div v-else class="h-8 px-3 text-xs text-muted-foreground bg-muted/30 rounded-md border border-border select-none cursor-pointer overflow-hidden leading-8 truncate" @click="startEmbKeyEdit">
                  {{ embApiKey || '未配置' }}
                </div>
                <button v-if="embKeyEditing" @click="embKeyVisible = !embKeyVisible"
                  class="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors" tabindex="-1">
                  <svg v-if="!embKeyVisible" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                </button>
              </div>
              <button v-if="!embKeyEditing && embApiKey && !embApiKey.includes('未')" @click="startEmbKeyEdit"
                class="shrink-0 text-[10px] text-muted-foreground hover:text-foreground px-1.5 py-1 rounded transition-colors" title="修改 API Key">修改</button>
            </div>
          </div>

          <!-- Embedding API Base (only for remote) -->
          <div v-if="embProvider !== 'local'" class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="Embedding API Base" :text="FIELD_DESC.embedding_api_base" /></div>
            <div class="w-56">
              <input v-model="embApiBase" type="text" placeholder="https://api.openai.com/v1" data-revert="embedding_api_base" @blur="revertOnBlur"
                class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
            </div>
          </div>

          <!-- Embedding model name with fetch + dropdown -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip label="嵌入模型" :text="FIELD_DESC.embedding_model" />
                <span v-if="isModified('embedding_model')" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
            <div class="w-56 flex items-center gap-1.5">
              <div class="relative flex-1 min-w-0">
                <input v-model="embModelSearch" :title="config.embedding_model" @input="config.embedding_model = (embProvider === 'local' ? 'local/' : '') + embModelSearch.replace(/^local\//, ''); embModelOpen = true"
                  @focus="handleEmbModelFocus" @blur="handleEmbModelBlur"
                  type="text" placeholder="local/BAAI/bge-small-en-v1.5"
                  class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
                <!-- Local mode dropdown: fastembed supported list -->
                <div v-if="embProvider === 'local' && embModelOpen && filteredLocalModels.length > 0"
                  class="absolute top-full left-0 right-0 mt-1 z-30 max-h-56 overflow-y-auto rounded-md border border-border bg-popover shadow-lg">
                  <button v-for="m in filteredLocalModels" :key="m.id" @mousedown.prevent="selectLocalModel(m)"
                    class="w-full text-left px-3 py-2 text-xs text-popover-foreground hover:bg-muted transition-colors border-b border-border/30 last:border-0"
                    :class="config.embedding_model === m.id ? 'bg-primary/5 font-medium' : ''">
                    <span class="flex items-center gap-1.5">
                      <span class="truncate" :title="m.name">{{ m.name }}</span>
                      <span v-if="m.cached" class="shrink-0 text-[9px] rounded px-1 py-0.5 bg-green-500/15 text-green-600 dark:text-green-400">已就绪</span>
                    </span>
                    <span class="flex items-center gap-2 text-[9px] text-muted-foreground/60 mt-0.5 truncate">
                      <span v-if="m.dim">{{ m.dim }} 维</span>
                      <span v-if="m.size_gb">{{ m.size_gb }} GB</span>
                      <span v-if="m.description" class="truncate" :title="m.description">{{ m.description }}</span>
                    </span>
                  </button>
                </div>
                <div v-if="embProvider === 'local' && embModelOpen && embLocalModels.length === 0 && !embFetchingLocal"
                  class="absolute top-full left-0 right-0 z-30 mt-1 rounded-md border border-border bg-popover shadow-lg px-3 py-2 text-xs text-muted-foreground/50 text-center">暂无可选模型</div>
                <!-- Remote mode dropdown -->
                <div v-if="embProvider !== 'local' && embModelOpen && filteredEmbModels.length > 0"
                  class="absolute top-full left-0 right-0 mt-1 z-30 max-h-48 overflow-y-auto rounded-md border border-border bg-popover shadow-lg">
                  <button v-for="m in filteredEmbModels" :key="m.id" @mousedown.prevent="selectEmbModel(m)"
                    class="w-full text-left px-3 py-2 text-xs text-popover-foreground hover:bg-muted transition-colors border-b border-border/30 last:border-0"
                    :class="config.embedding_model === m.id ? 'bg-primary/5 font-medium' : ''">
                    <span class="block truncate" :title="m.name">{{ m.name }}</span>
                    <span class="block text-[9px] text-muted-foreground/50 truncate" :title="m.id">{{ m.id }}</span>
                  </button>
                </div>
                <div v-if="embProvider !== 'local' && embModelOpen && embFetchedModels.length > 0 && filteredEmbModels.length === 0"
                  class="absolute top-full left-0 right-0 z-30 mt-1 rounded-md border border-border bg-popover shadow-lg px-3 py-2 text-xs text-muted-foreground/50 text-center">无匹配模型</div>
              </div>
              <button @click="embProvider === 'local' ? fetchLocalModels() : fetchEmbModels()" :disabled="embProvider === 'local' ? embFetchingLocal : embFetchingModels"
                class="shrink-0 rounded-md w-8 h-8 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                :title="(embProvider === 'local' ? embFetchingLocal : embFetchingModels) ? '获取中...' : '刷新模型列表'">
                <svg v-if="embProvider === 'local' ? embFetchingLocal : embFetchingModels" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              </button>
            </div>
          </div>
          <!-- Download provider (local only) -->
          <div v-if="embProvider === 'local'" class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="下载提供商" :text="FIELD_DESC.embedding_download_provider" /></div>
            <div class="w-56">
              <input v-model="config.embedding_download_provider" type="text" placeholder="https://hf-mirror.com"
                class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground font-mono placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
            </div>
          </div>

          <!-- Local model progress -->
          <div v-if="embeddingBusy" class="rounded-lg border border-primary/20 bg-primary/5 px-3 py-3 space-y-2 animate-fade-in">
            <div class="flex items-center justify-between text-xs">
              <span class="text-muted-foreground inline-flex items-center gap-2">
                <svg class="animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                {{ embeddingStageText || '处理中…' }}
              </span>
              <span v-if="embeddingProgress !== null" class="text-muted-foreground/70 tabular-nums">{{ Math.round(embeddingProgress * 100) }}%</span>
            </div>
            <div class="h-1.5 rounded-full bg-muted-foreground/15 overflow-hidden">
              <div class="h-full rounded-full bg-primary transition-all duration-300"
                :style="{ width: (embeddingProgress !== null ? embeddingProgress : 0.05) * 100 + '%' }" />
            </div>
            <p class="text-[10px] text-muted-foreground/60">本地模型首次使用需下载，完成后将自动重建知识库索引，使 Agent 能正常检索文档。</p>
          </div>

          <div class="flex items-center justify-between gap-2 pt-3 border-t border-border/50">
            <span v-if="sectionDiffCount('embed') > 0" class="text-[10px] text-amber-600 dark:text-amber-400">已修改 {{ sectionDiffCount('embed') }} 项</span>
            <span v-else class="text-[10px] text-muted-foreground/50">无修改</span>
            <button @click="saveSection('embed')" :disabled="saving || embeddingBusy || !sectionCanSave('embed')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
              <svg v-if="saving || embeddingBusy" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              {{ saving || embeddingBusy ? '处理中...' : '保存本区' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Retrieval -->
      <div v-show="activeTab === 'retrieval'" class="rounded-xl border border-border bg-card overflow-hidden">
        <div class="px-5 py-4 border-b border-border/50 bg-muted/20">
          <div class="flex items-center justify-between">
            <div><h3 class="text-sm font-semibold">检索参数</h3><p class="text-xs text-muted-foreground mt-0.5">知识库检索行为控制，影响召回质量和 Token 消耗</p></div>
            <div class="flex items-center gap-2 shrink-0">
              <button @click="resetSection('retrieval')" :disabled="resettingSection !== null || !sectionCanReset('retrieval')"
                class="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground border border-border rounded-md px-2 py-1 transition-colors disabled:opacity-40"
                title="恢复本分区为环境变量默认值（不影响其它分区）">
                <svg v-if="resettingSection === 'retrieval'" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                恢复默认
              </button>
              <div v-if="['top_k','score_threshold','chunk_size','chunk_overlap'].some(k => isModified(k))" class="text-[10px] text-amber-500 bg-amber-500/10 rounded-md px-2 py-0.5 font-medium">已修改</div>
            </div>
          </div>
        </div>
        <div class="px-5 py-4 space-y-4">
          <div v-for="f in [{key:'top_k',label:'检索返回数 (Top-K)',min:1,max:20,step:1},{key:'score_threshold',label:'相似度阈值',min:0,max:1,step:0.05}]" :key="f.key"
            class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip :label="f.label" :text="FIELD_DESC[f.key] || '配置项说明'" />
                <span v-if="isModified(f.key)" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
            <div class="w-56 flex items-center gap-3">
              <input :value="config[f.key]" @input="config[f.key] = parseFloat(($event.target as HTMLInputElement).value)" type="range" :min="f.min" :max="f.max" :step="f.step"
                class="flex-1 h-1.5 appearance-none rounded-full bg-muted-foreground/20 accent-primary cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer" />
              <span class="text-xs font-mono text-muted-foreground tabular-nums w-12 text-right">{{ config[f.key] }}</span>
            </div>
          </div>
          <div v-for="f in [{key:'chunk_size',label:'文档分块大小',min:100,max:2000,step:50,unit:'字符'},{key:'chunk_overlap',label:'分块重叠',min:0,max:500,step:10,unit:'字符'}]" :key="f.key"
            class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <ConfigTooltip :label="f.label" :text="FIELD_DESC[f.key] || '配置项说明'" />
                <span v-if="isModified(f.key)" class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              </div>
            </div>
            <div class="w-56 flex items-center gap-2">
              <input :value="config[f.key]" @input="config[f.key] = parseInt(($event.target as HTMLInputElement).value) || 0" type="number" :min="f.min" :max="f.max" :step="f.step"
                class="flex-1 h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground text-center tabular-nums focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <span class="text-[10px] text-muted-foreground whitespace-nowrap">{{ f.unit }}</span>
            </div>
          </div>
          <div class="flex items-center justify-between gap-2 pt-3 border-t border-border/50">
            <span v-if="sectionDiffCount('retrieval') > 0" class="text-[10px] text-amber-600 dark:text-amber-400">已修改 {{ sectionDiffCount('retrieval') }} 项</span>
            <span v-else class="text-[10px] text-muted-foreground/50">无修改</span>
            <button @click="saveSection('retrieval')" :disabled="saving || !sectionCanSave('retrieval')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
              <svg v-if="saving" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              {{ saving ? '保存中...' : '保存本区' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Agent Behavior -->
      <div v-show="activeTab === 'agent'" class="rounded-xl border border-border bg-card overflow-hidden">
        <div class="px-5 py-4 border-b border-border/50 bg-muted/20">
          <div class="flex items-center justify-between">
            <div><h3 class="text-sm font-semibold">Agent 行为</h3><p class="text-xs text-muted-foreground mt-0.5">AI Agent 的回复风格和工具使用控制</p></div>
            <div class="flex items-center gap-2 shrink-0">
              <button @click="resetSection('agent')" :disabled="resettingSection !== null || !sectionCanReset('agent')"
                class="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground border border-border rounded-md px-2 py-1 transition-colors disabled:opacity-40"
                title="恢复本分区为环境变量默认值（不影响其它分区）">
                <svg v-if="resettingSection === 'agent'" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                恢复默认
              </button>
              <div v-if="['system_prompt','enable_web_search','enable_knowledge_search','enable_summarize','enable_time_tool','max_tool_rounds'].some(k => isModified(k))"
                class="text-[10px] text-amber-500 bg-amber-500/10 rounded-md px-2 py-0.5 font-medium">已修改</div>
            </div>
          </div>
        </div>
        <div class="px-5 py-4 space-y-4">
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="系统提示词 (System Prompt)" :text="FIELD_DESC.system_prompt" /></div>
            <div class="w-56">
              <input v-model="config.system_prompt" type="text" placeholder="留空使用默认系统提示词" data-revert="system_prompt" @blur="revertOnBlur"
                class="w-full h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30" />
            </div>
          </div>
          <div v-for="f in [{key:'enable_web_search',label:'网页搜索'},{key:'enable_knowledge_search',label:'知识库检索'},{key:'enable_summarize',label:'摘要生成'},{key:'enable_time_tool',label:'时间查询'}]" :key="f.key"
            class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip :label="f.label" :text="FIELD_DESC[f.key] || '配置项说明'" /></div>
            <button @click="config[f.key] = !config[f.key]"
              class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
              :class="config[f.key] ? 'bg-primary' : 'bg-input'" role="switch" :aria-checked="config[f.key]">
              <span class="pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform"
                :class="config[f.key] ? 'translate-x-[18px]' : 'translate-x-[2px]'" />
            </button>
          </div>
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0"><ConfigTooltip label="最大工具调用轮次" :text="FIELD_DESC.max_tool_rounds" /></div>
            <div class="w-56 flex items-center gap-3">
              <input v-model.number="config.max_tool_rounds" type="range" min="1" max="10" step="1"
                class="flex-1 h-1.5 appearance-none rounded-full bg-muted-foreground/20 accent-primary cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer" />
              <span class="text-xs font-mono text-muted-foreground tabular-nums w-12 text-right">{{ config.max_tool_rounds }}</span>
            </div>
          </div>
            <div class="flex items-center justify-between gap-2 pt-3 border-t border-border/50">
              <span v-if="sectionDiffCount('agent') > 0" class="text-[10px] text-amber-600 dark:text-amber-400">已修改 {{ sectionDiffCount('agent') }} 项</span>
              <span v-else class="text-[10px] text-muted-foreground/50">无修改</span>
              <button @click="saveSection('agent')" :disabled="saving || !sectionCanSave('agent')"
                class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
                <svg v-if="saving" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                {{ saving ? '保存中...' : '保存本区' }}
              </button>
            </div>
        </div>
      </div>
          </div>
        </Transition>
    </div>
    </div>
  </div>
</template>

<style scoped>
/* Section tab switch transition: slide + fade */
.sect-slide-enter-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.sect-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.sect-slide-enter-from {
  opacity: 0;
  transform: translateX(14px);
}
.sect-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}
</style>
