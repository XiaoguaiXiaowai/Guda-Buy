<script setup lang="ts">
import type { FormInstance, FormRules, UploadFile } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

import {
  changeCmsPageStatus,
  createCmsAnnouncement,
  createCmsBanner,
  createCmsPage,
  createCmsSection,
  deleteCmsAnnouncement,
  deleteCmsBanner,
  deleteCmsPage,
  deleteCmsSection,
  fetchAdminCmsAnnouncements,
  fetchAdminCmsBanners,
  fetchAdminCmsPages,
  fetchAdminCmsSections,
  updateCmsAnnouncement,
  updateCmsBanner,
  updateCmsPage,
  updateCmsSection,
  uploadCmsBannerImage,
} from '@/api/cms'
import RichTextEditor from '@/components/RichTextEditor.vue'
import type {
  AdminCmsAnnouncement,
  AdminCmsBanner,
  AdminCmsPage,
  AdminCmsSection,
  CmsBannerPosition,
  CmsPageStatus,
} from '@/types/cms'
import {
  announcementLevelLabel,
  announcementLevelTone,
  bannerPositionLabel,
  bannerWindowLabel,
  bannerWindowState,
  bannerWindowTone,
  cmsPageStatusLabel,
  cmsPageStatusTone,
  isValidCmsSlug,
  sectionStatusLabel,
} from '@/utils/cms'
import { resolveImageUrl, toQueryParams } from '@/utils/catalog'
import { formatDateTime } from '@/utils/format'

type TabName = 'pages' | 'sections' | 'banners' | 'announcements'

const activeTab = ref<TabName>('pages')
const sections = ref<AdminCmsSection[]>([])
const pages = ref<AdminCmsPage[]>([])
const pageTotal = ref(0)
const banners = ref<AdminCmsBanner[]>([])
const announcements = ref<AdminCmsAnnouncement[]>([])

const sectionsLoading = ref(false)
const pagesLoading = ref(false)
const bannersLoading = ref(false)
const announcementsLoading = ref(false)

const pageFilters = reactive({ status: '', section: '', search: '', page: 1, pageSize: 10 })

const sectionOptions = computed(() => sections.value)
const pageStatusOptions: { label: string; value: CmsPageStatus }[] = [
  { label: '草稿', value: 'DRAFT' },
  { label: '已发布', value: 'PUBLISHED' },
  { label: '已下线', value: 'OFFLINE' },
]

// ---------------------------------------------------------------------------
// 栏目
// ---------------------------------------------------------------------------
const sectionDialog = ref(false)
const sectionSaving = ref(false)
const sectionEditingId = ref<string | null>(null)
const sectionFormRef = ref<FormInstance>()
const sectionForm = reactive({
  name: '',
  slug: '',
  sort_weight: 0,
  status: 'ENABLED' as 'ENABLED' | 'DISABLED',
})
const sectionRules: FormRules = {
  name: [{ required: true, message: '请输入栏目名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入栏目标识', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (isValidCmsSlug(value)) {
          callback()
        } else {
          callback(new Error('仅限小写字母、数字和连字符'))
        }
      },
      trigger: 'blur',
    },
  ],
}

async function loadSections() {
  sectionsLoading.value = true
  try {
    sections.value = await fetchAdminCmsSections()
  } finally {
    sectionsLoading.value = false
  }
}

async function openSectionCreate() {
  sectionEditingId.value = null
  Object.assign(sectionForm, { name: '', slug: '', sort_weight: 0, status: 'ENABLED' })
  sectionDialog.value = true
  await nextTick()
  sectionFormRef.value?.clearValidate()
}

async function openSectionEdit(section: AdminCmsSection) {
  sectionEditingId.value = section.public_id
  Object.assign(sectionForm, {
    name: section.name,
    slug: section.slug,
    sort_weight: section.sort_weight,
    status: section.status,
  })
  sectionDialog.value = true
  await nextTick()
  sectionFormRef.value?.clearValidate()
}

async function saveSection() {
  if (!sectionFormRef.value) {
    return
  }
  const valid = await sectionFormRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  sectionSaving.value = true
  try {
    if (sectionEditingId.value) {
      await updateCmsSection(sectionEditingId.value, { ...sectionForm })
      ElMessage.success('栏目已更新')
    } else {
      await createCmsSection({ ...sectionForm })
      ElMessage.success('栏目已创建')
    }
    sectionDialog.value = false
    await loadSections()
  } finally {
    sectionSaving.value = false
  }
}

async function removeSection(section: AdminCmsSection) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除栏目「${section.name}」吗？栏目下存在页面时不可删除。`,
    '删除栏目',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteCmsSection(section.public_id)
  ElMessage.success('栏目已删除')
  await loadSections()
}

// ---------------------------------------------------------------------------
// 页面
// ---------------------------------------------------------------------------
const pageDialog = ref(false)
const pageSaving = ref(false)
const pageEditingId = ref<string | null>(null)
const pageFormRef = ref<FormInstance>()
const pageForm = reactive({
  section_public_id: '',
  title: '',
  slug: '',
  sort_weight: 0,
  seo_title: '',
  seo_description: '',
  content: '',
})
const pageRules: FormRules = {
  section_public_id: [{ required: true, message: '请选择栏目', trigger: 'change' }],
  title: [{ required: true, message: '请输入页面标题', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入页面标识', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (isValidCmsSlug(value)) {
          callback()
        } else {
          callback(new Error('仅限小写字母、数字和连字符'))
        }
      },
      trigger: 'blur',
    },
  ],
}

async function loadPages() {
  pagesLoading.value = true
  try {
    const data = await fetchAdminCmsPages(
      toQueryParams({
        status: pageFilters.status,
        section: pageFilters.section,
        search: pageFilters.search.trim(),
        page: pageFilters.page,
        page_size: pageFilters.pageSize,
      }),
    )
    pages.value = data.results
    pageTotal.value = data.count
  } finally {
    pagesLoading.value = false
  }
}

function applyPageFilters() {
  pageFilters.page = 1
  void loadPages()
}

function handlePageChange(page: number) {
  pageFilters.page = page
  void loadPages()
}

async function openPageCreate() {
  if (!sections.value.length) {
    ElMessage.warning('请先创建栏目')
    return
  }
  pageEditingId.value = null
  Object.assign(pageForm, {
    section_public_id: sections.value[0]?.public_id ?? '',
    title: '',
    slug: '',
    sort_weight: 0,
    seo_title: '',
    seo_description: '',
    content: '',
  })
  pageDialog.value = true
  await nextTick()
  pageFormRef.value?.clearValidate()
}

async function openPageEdit(page: AdminCmsPage) {
  pageEditingId.value = page.public_id
  Object.assign(pageForm, {
    section_public_id: page.section.public_id,
    title: page.title,
    slug: page.slug,
    sort_weight: page.sort_weight,
    seo_title: page.seo_title,
    seo_description: page.seo_description,
    content: page.content,
  })
  pageDialog.value = true
  await nextTick()
  pageFormRef.value?.clearValidate()
}

async function savePage() {
  if (!pageFormRef.value) {
    return
  }
  const valid = await pageFormRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  pageSaving.value = true
  try {
    if (pageEditingId.value) {
      await updateCmsPage(pageEditingId.value, { ...pageForm })
      ElMessage.success('页面已保存，发布后前台生效')
    } else {
      await createCmsPage({ ...pageForm })
      ElMessage.success('页面草稿已创建')
    }
    pageDialog.value = false
    await loadPages()
  } finally {
    pageSaving.value = false
  }
}

async function togglePublish(page: AdminCmsPage) {
  const publishing = page.status !== 'PUBLISHED'
  if (!publishing) {
    const confirmed = await ElMessageBox.confirm(
      `确定下线「${page.title}」吗？下线后前台立即不可见。`,
      '下线页面',
      { type: 'warning', confirmButtonText: '下线', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return
    }
  }
  await changeCmsPageStatus(page.public_id, publishing ? 'PUBLISH' : 'OFFLINE')
  ElMessage.success(publishing ? '页面已发布' : '页面已下线')
  await loadPages()
}

async function removePage(page: AdminCmsPage) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除页面「${page.title}」吗？已发布页面需先下线。`,
    '删除页面',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteCmsPage(page.public_id)
  ElMessage.success('页面已删除')
  await loadPages()
}

// ---------------------------------------------------------------------------
// 轮播位
// ---------------------------------------------------------------------------
const bannerDialog = ref(false)
const bannerSaving = ref(false)
const bannerEditingId = ref<string | null>(null)
const bannerFormRef = ref<FormInstance>()
const pendingBannerImage = ref<File | null>(null)
const bannerPreview = ref('')
const bannerForm = reactive({
  title: '',
  position: 'HOME_TOP' as CmsBannerPosition,
  link_url: '',
  sort_weight: 0,
  status: 'ENABLED' as 'ENABLED' | 'DISABLED',
  start_at: '' as string,
  end_at: '' as string,
})
const bannerRules: FormRules = {
  position: [{ required: true, message: '请选择展示位置', trigger: 'change' }],
}

async function loadBanners() {
  bannersLoading.value = true
  try {
    banners.value = await fetchAdminCmsBanners()
  } finally {
    bannersLoading.value = false
  }
}

async function openBannerCreate() {
  bannerEditingId.value = null
  pendingBannerImage.value = null
  bannerPreview.value = ''
  Object.assign(bannerForm, {
    title: '',
    position: 'HOME_TOP',
    link_url: '',
    sort_weight: 0,
    status: 'ENABLED',
    start_at: '',
    end_at: '',
  })
  bannerDialog.value = true
  await nextTick()
  bannerFormRef.value?.clearValidate()
}

async function openBannerEdit(banner: AdminCmsBanner) {
  bannerEditingId.value = banner.public_id
  pendingBannerImage.value = null
  bannerPreview.value = resolveImageUrl(banner.image)
  Object.assign(bannerForm, {
    title: banner.title,
    position: banner.position,
    link_url: banner.link_url,
    sort_weight: banner.sort_weight,
    status: banner.status,
    start_at: banner.start_at ?? '',
    end_at: banner.end_at ?? '',
  })
  bannerDialog.value = true
  await nextTick()
  bannerFormRef.value?.clearValidate()
}

function handleBannerFile(uploadFile: UploadFile) {
  if (!uploadFile.raw) {
    return
  }
  pendingBannerImage.value = uploadFile.raw
  bannerPreview.value = URL.createObjectURL(uploadFile.raw)
}

async function saveBanner() {
  if (!bannerFormRef.value) {
    return
  }
  const valid = await bannerFormRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  if (!bannerEditingId.value && !pendingBannerImage.value) {
    ElMessage.warning('请选择轮播图片')
    return
  }
  bannerSaving.value = true
  try {
    const payload = {
      title: bannerForm.title,
      position: bannerForm.position,
      link_url: bannerForm.link_url,
      sort_weight: bannerForm.sort_weight,
      status: bannerForm.status,
      start_at: bannerForm.start_at || null,
      end_at: bannerForm.end_at || null,
    }
    let targetId = bannerEditingId.value
    if (targetId) {
      await updateCmsBanner(targetId, payload)
    } else {
      const created = await createCmsBanner({ ...payload, image: '' })
      targetId = created.public_id
    }
    if (pendingBannerImage.value) {
      await uploadCmsBannerImage(targetId, pendingBannerImage.value)
    }
    ElMessage.success(bannerEditingId.value ? '轮播已更新' : '轮播已创建')
    bannerDialog.value = false
    await loadBanners()
  } finally {
    bannerSaving.value = false
  }
}

async function removeBanner(banner: AdminCmsBanner) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除轮播「${banner.title || banner.image}」吗？`,
    '删除轮播',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteCmsBanner(banner.public_id)
  ElMessage.success('轮播已删除')
  await loadBanners()
}

// ---------------------------------------------------------------------------
// 公告
// ---------------------------------------------------------------------------
const announcementDialog = ref(false)
const announcementSaving = ref(false)
const announcementEditingId = ref<string | null>(null)
const announcementFormRef = ref<FormInstance>()
const announcementForm = reactive({
  title: '',
  content: '',
  level: 'NORMAL' as 'NORMAL' | 'IMPORTANT',
  status: 'ENABLED' as 'ENABLED' | 'DISABLED',
})
const announcementRules: FormRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
}

async function loadAnnouncements() {
  announcementsLoading.value = true
  try {
    announcements.value = await fetchAdminCmsAnnouncements()
  } finally {
    announcementsLoading.value = false
  }
}

async function openAnnouncementCreate() {
  announcementEditingId.value = null
  Object.assign(announcementForm, {
    title: '',
    content: '',
    level: 'NORMAL',
    status: 'ENABLED',
  })
  announcementDialog.value = true
  await nextTick()
  announcementFormRef.value?.clearValidate()
}

async function openAnnouncementEdit(announcement: AdminCmsAnnouncement) {
  announcementEditingId.value = announcement.public_id
  Object.assign(announcementForm, {
    title: announcement.title,
    content: announcement.content,
    level: announcement.level,
    status: announcement.status,
  })
  announcementDialog.value = true
  await nextTick()
  announcementFormRef.value?.clearValidate()
}

async function saveAnnouncement() {
  if (!announcementFormRef.value) {
    return
  }
  const valid = await announcementFormRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  announcementSaving.value = true
  try {
    if (announcementEditingId.value) {
      await updateCmsAnnouncement(announcementEditingId.value, { ...announcementForm })
      ElMessage.success('公告已更新')
    } else {
      await createCmsAnnouncement({ ...announcementForm })
      ElMessage.success('公告已创建')
    }
    announcementDialog.value = false
    await loadAnnouncements()
  } finally {
    announcementSaving.value = false
  }
}

async function removeAnnouncement(announcement: AdminCmsAnnouncement) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除公告「${announcement.title}」吗？`,
    '删除公告',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteCmsAnnouncement(announcement.public_id)
  ElMessage.success('公告已删除')
  await loadAnnouncements()
}

onMounted(async () => {
  await Promise.all([loadSections(), loadPages(), loadBanners(), loadAnnouncements()])
})
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__header">
      <div>
        <p class="admin-page__eyebrow">内容后台</p>
        <h1>内容运营</h1>
        <p class="admin-page__desc">
          维护栏目与页面、首页轮播与公告；页面发布/下线后前台缓存立即失效。
        </p>
      </div>
    </header>

    <el-tabs v-model="activeTab" class="cms-tabs">
      <!-- 页面 -->
      <el-tab-pane label="页面" name="pages">
        <div class="cms-toolbar">
          <el-select
            v-model="pageFilters.status"
            placeholder="全部状态"
            clearable
            style="width: 130px"
            @change="applyPageFilters"
          >
            <el-option
              v-for="item in pageStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="pageFilters.section"
            placeholder="全部栏目"
            clearable
            style="width: 160px"
            @change="applyPageFilters"
          >
            <el-option
              v-for="section in sectionOptions"
              :key="section.public_id"
              :label="section.name"
              :value="section.public_id"
            />
          </el-select>
          <el-input
            v-model="pageFilters.search"
            placeholder="搜索标题或 slug"
            clearable
            style="width: 220px"
            @keyup.enter="applyPageFilters"
            @clear="applyPageFilters"
          />
          <el-button @click="applyPageFilters">筛选</el-button>
          <el-button type="primary" class="cms-toolbar__spacer" @click="openPageCreate">
            新建页面
          </el-button>
        </div>

        <el-table v-loading="pagesLoading" :data="pages" border stripe>
          <el-table-column prop="title" label="标题" min-width="180" />
          <el-table-column prop="slug" label="slug" min-width="150" />
          <el-table-column label="栏目" min-width="120">
            <template #default="{ row }">{{ row.section.name }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="cmsPageStatusTone(row.status)" effect="plain" size="small">
                {{ cmsPageStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="210" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                :type="row.status === 'PUBLISHED' ? 'warning' : 'success'"
                @click="togglePublish(row)"
              >
                {{ row.status === 'PUBLISHED' ? '下线' : '发布' }}
              </el-button>
              <el-button link type="primary" @click="openPageEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removePage(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="pageTotal > pageFilters.pageSize"
          class="cms-pagination"
          layout="prev, pager, next"
          :total="pageTotal"
          :page-size="pageFilters.pageSize"
          :current-page="pageFilters.page"
          @current-change="handlePageChange"
        />
      </el-tab-pane>

      <!-- 栏目 -->
      <el-tab-pane label="栏目" name="sections">
        <div class="cms-toolbar">
          <el-button type="primary" class="cms-toolbar__spacer" @click="openSectionCreate">
            新建栏目
          </el-button>
        </div>
        <el-table v-loading="sectionsLoading" :data="sections" border stripe>
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="slug" label="slug" min-width="150" />
          <el-table-column prop="sort_weight" label="排序" width="90" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'ENABLED' ? 'success' : 'info'"
                effect="plain"
                size="small"
              >
                {{ sectionStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="page_count" label="页面数" width="100" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openSectionEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeSection(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 轮播 -->
      <el-tab-pane label="轮播" name="banners">
        <div class="cms-toolbar">
          <el-button type="primary" class="cms-toolbar__spacer" @click="openBannerCreate">
            新建轮播
          </el-button>
        </div>
        <el-table v-loading="bannersLoading" :data="banners" border stripe>
          <el-table-column label="图片" width="130">
            <template #default="{ row }">
              <img
                v-if="row.image"
                class="cms-thumb"
                :src="resolveImageUrl(row.image)"
                :alt="row.title || '轮播'"
              />
              <span v-else class="cms-thumb cms-thumb--empty">未上传</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="140" />
          <el-table-column label="位置" width="110">
            <template #default="{ row }">{{ bannerPositionLabel(row.position) }}</template>
          </el-table-column>
          <el-table-column label="展示窗口" width="130">
            <template #default="{ row }">
              <el-tag :type="bannerWindowTone(bannerWindowState(row))" effect="plain" size="small">
                {{ bannerWindowLabel(bannerWindowState(row)) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sort_weight" label="权重" width="80" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'ENABLED' ? 'success' : 'info'"
                effect="plain"
                size="small"
              >
                {{ row.status === 'ENABLED' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openBannerEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeBanner(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 公告 -->
      <el-tab-pane label="公告" name="announcements">
        <div class="cms-toolbar">
          <el-button type="primary" class="cms-toolbar__spacer" @click="openAnnouncementCreate">
            新建公告
          </el-button>
        </div>
        <el-table v-loading="announcementsLoading" :data="announcements" border stripe>
          <el-table-column prop="title" label="标题" min-width="200" />
          <el-table-column label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="announcementLevelTone(row.level)" effect="plain" size="small">
                {{ announcementLevelLabel(row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'ENABLED' ? 'success' : 'info'"
                effect="plain"
                size="small"
              >
                {{ row.status === 'ENABLED' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openAnnouncementEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeAnnouncement(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 栏目弹窗 -->
    <el-dialog
      v-model="sectionDialog"
      :title="sectionEditingId ? '编辑栏目' : '新建栏目'"
      width="480px"
    >
      <el-form ref="sectionFormRef" :model="sectionForm" :rules="sectionRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="sectionForm.name" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="slug" prop="slug">
          <el-input v-model="sectionForm.slug" maxlength="64" placeholder="例如 help-center" />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="sectionForm.sort_weight" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="sectionForm.status"
            active-value="ENABLED"
            inactive-value="DISABLED"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sectionDialog = false">取消</el-button>
        <el-button type="primary" :loading="sectionSaving" @click="saveSection">保存</el-button>
      </template>
    </el-dialog>

    <!-- 页面弹窗 -->
    <el-dialog
      v-model="pageDialog"
      :title="pageEditingId ? '编辑页面' : '新建页面'"
      width="880px"
      top="6vh"
    >
      <el-form ref="pageFormRef" :model="pageForm" :rules="pageRules" label-width="90px">
        <el-form-item label="栏目" prop="section_public_id">
          <el-select v-model="pageForm.section_public_id" style="width: 260px">
            <el-option
              v-for="section in sectionOptions"
              :key="section.public_id"
              :label="section.name"
              :value="section.public_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="pageForm.title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="slug" prop="slug">
          <el-input v-model="pageForm.slug" maxlength="64" placeholder="例如 shipping-policy" />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="pageForm.sort_weight" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="SEO 标题">
          <el-input v-model="pageForm.seo_title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="SEO 描述">
          <el-input
            v-model="pageForm.seo_description"
            maxlength="255"
            show-word-limit
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="正文">
          <RichTextEditor v-model="pageForm.content" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="cms-dialog__hint">保存为草稿，发布后前台可访问 /page/{{ pageForm.slug }}</span>
        <el-button @click="pageDialog = false">取消</el-button>
        <el-button type="primary" :loading="pageSaving" @click="savePage">保存</el-button>
      </template>
    </el-dialog>

    <!-- 轮播弹窗 -->
    <el-dialog
      v-model="bannerDialog"
      :title="bannerEditingId ? '编辑轮播' : '新建轮播'"
      width="600px"
    >
      <el-form ref="bannerFormRef" :model="bannerForm" :rules="bannerRules" label-width="90px">
        <el-form-item label="展示位置" prop="position">
          <el-select v-model="bannerForm.position" style="width: 200px">
            <el-option label="首页顶部" value="HOME_TOP" />
            <el-option label="首页中部" value="HOME_MIDDLE" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="bannerForm.title" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="图片">
          <div class="cms-upload">
            <img
              v-if="bannerPreview"
              class="cms-upload__preview"
              :src="bannerPreview"
              alt="轮播预览"
            />
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="image/jpeg,image/png,image/webp"
              :on-change="handleBannerFile"
            >
              <el-button>{{ bannerPreview ? '更换图片' : '选择图片' }}</el-button>
            </el-upload>
            <span class="cms-upload__hint">jpg/png/webp，≤5MB，建议 16:9</span>
          </div>
        </el-form-item>
        <el-form-item label="跳转链接">
          <el-input v-model="bannerForm.link_url" placeholder="站内 /page/xxx 或 https://" />
        </el-form-item>
        <el-form-item label="展示时间">
          <el-date-picker
            v-model="bannerForm.start_at"
            type="datetime"
            placeholder="开始时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
          <span class="cms-upload__hint">至</span>
          <el-date-picker
            v-model="bannerForm.end_at"
            type="datetime"
            placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="bannerForm.sort_weight" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="bannerForm.status"
            active-value="ENABLED"
            inactive-value="DISABLED"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bannerDialog = false">取消</el-button>
        <el-button type="primary" :loading="bannerSaving" @click="saveBanner">保存</el-button>
      </template>
    </el-dialog>

    <!-- 公告弹窗 -->
    <el-dialog
      v-model="announcementDialog"
      :title="announcementEditingId ? '编辑公告' : '新建公告'"
      width="560px"
    >
      <el-form
        ref="announcementFormRef"
        :model="announcementForm"
        :rules="announcementRules"
        label-width="90px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="announcementForm.title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="正文">
          <el-input
            v-model="announcementForm.content"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="级别">
          <el-radio-group v-model="announcementForm.level">
            <el-radio value="NORMAL">普通</el-radio>
            <el-radio value="IMPORTANT">重要</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="announcementForm.status"
            active-value="ENABLED"
            inactive-value="DISABLED"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="announcementDialog = false">取消</el-button>
        <el-button type="primary" :loading="announcementSaving" @click="saveAnnouncement">
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped lang="scss">
.admin-page {
  &__header {
    margin-bottom: 20px;
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    letter-spacing: 2px;
    margin-bottom: 6px;
  }

  h1 {
    font-size: 26px;
    margin-bottom: 8px;
  }

  &__desc {
    color: var(--guda-text-muted);
    font-size: 14px;
  }
}

.cms-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;

  &__spacer {
    margin-left: auto;
  }
}

.cms-pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.cms-thumb {
  display: block;
  width: 96px;
  height: 54px;
  object-fit: cover;
  border-radius: 6px;
  background: var(--guda-bg);

  &--empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.cms-upload {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;

  &__preview {
    width: 160px;
    height: 90px;
    object-fit: cover;
    border-radius: 8px;
    border: 1px solid var(--guda-border);
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.cms-dialog__hint {
  float: left;
  color: var(--guda-text-muted);
  font-size: 12px;
  line-height: 32px;
}

.cms-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 20px;
  }
}
</style>
