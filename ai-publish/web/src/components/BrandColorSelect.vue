<template>
  <div class="brand-color-select">
    <el-select :model-value="preset" style="width: 100%" @change="onPresetChange">
      <el-option
        v-for="item in BRAND_COLORS"
        :key="item.value || 'none'"
        :label="item.label"
        :value="item.value"
      >
        <span v-if="item.swatch" class="color-dot" :style="{ backgroundColor: item.swatch }" />
        <span>{{ item.label }}</span>
        <span v-if="item.hint" class="color-hint">（{{ item.hint }}）</span>
      </el-option>
    </el-select>
    <el-input
      v-if="preset === BRAND_COLOR_CUSTOM"
      :model-value="modelValue"
      class="custom-input"
      placeholder="一般选上方即可；高级用户可填色号如 #2E8B57"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { BRAND_COLOR_CUSTOM, BRAND_COLORS, resolveBrandColorPreset } from '@/constants/imageStyles'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const preset = ref('')

watch(
  () => props.modelValue,
  (value) => {
    preset.value = resolveBrandColorPreset(value)
  },
  { immediate: true },
)

function onPresetChange(value) {
  preset.value = value
  if (value === BRAND_COLOR_CUSTOM) {
    if (!props.modelValue || BRAND_COLORS.some((item) => item.value === props.modelValue)) {
      emit('update:modelValue', '')
    }
    return
  }
  emit('update:modelValue', value || '')
}
</script>

<style scoped>
.brand-color-select {
  width: 100%;
}
.color-dot {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  margin-right: 8px;
  vertical-align: -2px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}
.color-hint {
  color: #909399;
  font-size: 12px;
  margin-left: 4px;
}
.custom-input {
  margin-top: 8px;
}
</style>
