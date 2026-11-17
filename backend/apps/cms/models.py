"""CMS 内容运营模型：栏目、页面、轮播位、公告（架构文档 7.3 / 10.9）。"""

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class CmsSection(BaseModel):
    """栏目：页面的一级归类，停用后前台不再展示其下页面。"""

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "启用"
        DISABLED = "DISABLED", "停用"

    name = models.CharField("栏目名称", max_length=60)
    slug = models.CharField("栏目标识", max_length=64, unique=True)
    sort_weight = models.IntegerField("排序权重", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED)

    class Meta:
        db_table = "cms_sections"
        verbose_name = "CMS 栏目"
        verbose_name_plural = "CMS 栏目"
        ordering = ["sort_weight", "id"]

    def __str__(self) -> str:
        return self.name


class CmsPage(BaseModel):
    """内容页面：正文为服务端白名单清洗后的 HTML，仅 PUBLISHED 对外可见。"""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        PUBLISHED = "PUBLISHED", "已发布"
        OFFLINE = "OFFLINE", "已下线"

    section = models.ForeignKey(
        CmsSection,
        on_delete=models.PROTECT,
        related_name="pages",
        verbose_name="所属栏目",
    )
    slug = models.CharField("页面标识", max_length=64, unique=True)
    title = models.CharField("页面标题", max_length=120)
    content = models.TextField("正文", blank=True, default="")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    seo_title = models.CharField("SEO 标题", max_length=120, blank=True, default="")
    seo_description = models.CharField("SEO 描述", max_length=255, blank=True, default="")
    sort_weight = models.IntegerField("排序权重", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="创建人",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="更新人",
    )

    class Meta:
        db_table = "cms_pages"
        verbose_name = "CMS 页面"
        verbose_name_plural = "CMS 页面"
        ordering = ["sort_weight", "-published_at", "-id"]
        permissions = [
            ("change_page", "可维护内容页面"),
            ("publish_page", "可发布或下线内容页面"),
        ]
        indexes = [
            models.Index(fields=["section", "status"], name="idx_cms_pages_section"),
            models.Index(fields=["status", "sort_weight"], name="idx_cms_pages_status"),
        ]

    def __str__(self) -> str:
        return self.title


class CmsBanner(BaseModel):
    """轮播位：仅在启用状态且当前时间处于展示窗口内对外可见。"""

    class Position(models.TextChoices):
        HOME_TOP = "HOME_TOP", "首页顶部"
        HOME_MIDDLE = "HOME_MIDDLE", "首页中部"

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "启用"
        DISABLED = "DISABLED", "停用"

    position = models.CharField(
        "展示位置",
        max_length=16,
        choices=Position.choices,
        default=Position.HOME_TOP,
    )
    title = models.CharField("标题", max_length=60, blank=True, default="")
    image = models.CharField("图片路径", max_length=255)
    link_url = models.CharField("跳转链接", max_length=255, blank=True, default="")
    sort_weight = models.IntegerField("排序权重", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED)
    start_at = models.DateTimeField("开始时间", null=True, blank=True)
    end_at = models.DateTimeField("结束时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="创建人",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="更新人",
    )

    class Meta:
        db_table = "cms_banners"
        verbose_name = "CMS 轮播位"
        verbose_name_plural = "CMS 轮播位"
        ordering = ["-sort_weight", "id"]
        indexes = [
            models.Index(fields=["status", "position"], name="idx_cms_banners_position"),
        ]

    def __str__(self) -> str:
        return self.title or self.image


class CmsAnnouncement(BaseModel):
    """公告：启用后按发布时间倒序展示，IMPORTANT 级别前台高亮。"""

    class Level(models.TextChoices):
        NORMAL = "NORMAL", "普通"
        IMPORTANT = "IMPORTANT", "重要"

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "启用"
        DISABLED = "DISABLED", "停用"

    title = models.CharField("标题", max_length=120)
    content = models.TextField("正文", blank=True, default="")
    level = models.CharField("级别", max_length=16, choices=Level.choices, default=Level.NORMAL)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)

    class Meta:
        db_table = "cms_announcements"
        verbose_name = "CMS 公告"
        verbose_name_plural = "CMS 公告"
        ordering = ["-published_at", "-id"]
        indexes = [
            models.Index(fields=["status", "published_at"], name="idx_cms_announcements_status"),
        ]

    def __str__(self) -> str:
        return self.title
