<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    minHeight?: number
  }>(),
  {
    placeholder: '输入正文，支持加粗、标题、列表、链接与图片',
    minHeight: 320,
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = ref<HTMLElement | null>(null)

function sync() {
  emit('update:modelValue', editor.value?.innerHTML ?? '')
}

function apply(command: string, value?: string) {
  editor.value?.focus()
  document.execCommand(command, false, value)
  sync()
}

function insertLink() {
  const url = window.prompt('请输入链接地址（站内路径或 https://）', '/')
  if (url) {
    apply('createLink', url)
  }
}

function insertImage() {
  const url = window.prompt('请输入图片地址（/media/... 或已授权域名）')
  if (url) {
    apply('insertImage', url)
  }
}

function setBlock(tag: 'p' | 'h2' | 'h3') {
  apply('formatBlock', `<${tag}>`)
}

onMounted(() => {
  if (editor.value && editor.value.innerHTML !== props.modelValue) {
    editor.value.innerHTML = props.modelValue
  }
})

watch(
  () => props.modelValue,
  (value) => {
    if (editor.value && editor.value.innerHTML !== value) {
      editor.value.innerHTML = value
    }
  },
)
</script>

<template>
  <div class="rte">
    <div class="rte__toolbar">
      <el-button size="small" text @click="apply('bold')">加粗</el-button>
      <el-button size="small" text @click="apply('italic')">斜体</el-button>
      <el-button size="small" text @click="setBlock('h2')">标题</el-button>
      <el-button size="small" text @click="setBlock('h3')">小标题</el-button>
      <el-button size="small" text @click="apply('insertUnorderedList')">列表</el-button>
      <el-button size="small" text @click="insertLink">链接</el-button>
      <el-button size="small" text @click="insertImage">图片</el-button>
      <el-button size="small" text @click="apply('removeFormat')">清除格式</el-button>
    </div>
    <div
      ref="editor"
      class="rte__body"
      contenteditable="true"
      role="textbox"
      aria-multiline="true"
      :data-placeholder="placeholder"
      :style="{ minHeight: `${minHeight}px` }"
      @input="sync"
      @blur="sync"
    />
    <p class="rte__hint">正文会在保存时经服务端白名单清洗，脚本与未授权外链图片会被移除。</p>
  </div>
</template>

<style scoped lang="scss">
.rte {
  border: 1px solid var(--guda-border);
  border-radius: 8px;
  background: var(--guda-surface);

  &__toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    padding: 6px 8px;
    border-bottom: 1px solid var(--guda-border);
  }

  &__body {
    padding: 14px 16px;
    outline: none;
    line-height: 1.8;
    font-size: 14px;

    &:empty::before {
      content: attr(data-placeholder);
      color: var(--guda-text-muted);
    }

    :deep(h2) {
      font-size: 20px;
      margin: 12px 0 8px;
    }

    :deep(h3) {
      font-size: 16px;
      margin: 10px 0 6px;
    }

    :deep(p) {
      margin: 0 0 8px;
    }

    :deep(ul),
    :deep(ol) {
      padding-left: 20px;
    }

    :deep(img) {
      max-width: 100%;
    }

    :deep(a) {
      color: var(--guda-primary);
    }
  }

  &__hint {
    padding: 8px 16px;
    border-top: 1px dashed var(--guda-border);
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}
</style>
