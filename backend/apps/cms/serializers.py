"""CMS 入参校验与出参序列化。"""

from rest_framework import serializers

from apps.cms.models import CmsAnnouncement, CmsBanner, CmsPage, CmsSection


# ---------------------------------------------------------------------------
# 前台输出
# ---------------------------------------------------------------------------
class CmsSectionBriefSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()


class CmsPagePublicSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    slug = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    seo_title = serializers.CharField()
    seo_description = serializers.CharField()
    section = CmsSectionBriefSerializer()
    published_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField()


class CmsBannerPublicSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    position = serializers.CharField()
    title = serializers.CharField()
    image = serializers.CharField()
    link_url = serializers.CharField()
    sort_weight = serializers.IntegerField()


class CmsAnnouncementPublicSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    level = serializers.CharField()
    published_at = serializers.DateTimeField(allow_null=True)


class CmsHomeSerializer(serializers.Serializer):
    banners = CmsBannerPublicSerializer(many=True)
    announcements = CmsAnnouncementPublicSerializer(many=True)
    recommended_products = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# 后台输出
# ---------------------------------------------------------------------------
class AdminSectionSerializer(serializers.ModelSerializer):
    page_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CmsSection
        fields = [
            "public_id",
            "name",
            "slug",
            "sort_weight",
            "status",
            "page_count",
            "created_at",
            "updated_at",
        ]


class AdminPageSerializer(serializers.ModelSerializer):
    section = AdminSectionSerializer(read_only=True)

    class Meta:
        model = CmsPage
        fields = [
            "public_id",
            "slug",
            "title",
            "content",
            "status",
            "published_at",
            "seo_title",
            "seo_description",
            "sort_weight",
            "section",
            "created_at",
            "updated_at",
        ]


class AdminBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CmsBanner
        fields = [
            "public_id",
            "position",
            "title",
            "image",
            "link_url",
            "sort_weight",
            "status",
            "start_at",
            "end_at",
            "created_at",
            "updated_at",
        ]


class AdminAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CmsAnnouncement
        fields = [
            "public_id",
            "title",
            "content",
            "level",
            "status",
            "published_at",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class SectionWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    slug = serializers.CharField(max_length=64)
    sort_weight = serializers.IntegerField(required=False, default=0)
    status = serializers.ChoiceField(
        choices=CmsSection.Status.choices, required=False, default=CmsSection.Status.ENABLED
    )


class PageWriteSerializer(serializers.Serializer):
    section_public_id = serializers.CharField(max_length=32)
    slug = serializers.CharField(max_length=64)
    title = serializers.CharField(max_length=120)
    content = serializers.CharField(required=False, allow_blank=True, default="")
    seo_title = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    seo_description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    sort_weight = serializers.IntegerField(required=False, default=0)


class PageStatusSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["PUBLISH", "OFFLINE"], required=False, default="PUBLISH"
    )


class BannerWriteSerializer(serializers.Serializer):
    position = serializers.ChoiceField(
        choices=CmsBanner.Position.choices, required=False, default=CmsBanner.Position.HOME_TOP
    )
    title = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    image = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    link_url = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    sort_weight = serializers.IntegerField(required=False, default=0)
    status = serializers.ChoiceField(
        choices=CmsBanner.Status.choices, required=False, default=CmsBanner.Status.ENABLED
    )
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    end_at = serializers.DateTimeField(required=False, allow_null=True)


class BannerImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class AnnouncementWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    content = serializers.CharField(required=False, allow_blank=True, default="")
    level = serializers.ChoiceField(
        choices=CmsAnnouncement.Level.choices, required=False, default=CmsAnnouncement.Level.NORMAL
    )
    status = serializers.ChoiceField(
        choices=CmsAnnouncement.Status.choices,
        required=False,
        default=CmsAnnouncement.Status.ENABLED,
    )
