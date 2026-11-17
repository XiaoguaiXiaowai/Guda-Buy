"""CMS 富文本白名单清洗：剥离危险标签、事件属性与未授权外链图片（架构文档 10.9）。

只依赖标准库 html.parser，避免引入额外清洗依赖；输出统一为转义后的安全 HTML。
"""

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.conf import settings

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "img",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
VOID_TAGS = {"br", "img"}
# 标签本身与其内部文本都不允许保留
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript"}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}
SAFE_LINK_SCHEMES = ("http://", "https://", "mailto:")
SAFE_IMAGE_SCHEMES = ("http://", "https://")

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _allowed_image_hosts() -> set[str]:
    hosts = {host.strip().lower() for host in settings.CMS_ALLOWED_IMAGE_HOSTS if host.strip()}
    site_host = urlparse(getattr(settings, "APP_SITE_URL", "")).hostname
    if site_host:
        hosts.add(site_host.lower())
    return hosts


def _safe_link(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered.startswith(("javascript:", "data:", "vbscript:")):
        return None
    if value.startswith(("/", "#")):
        return value
    if lowered.startswith(SAFE_LINK_SCHEMES):
        return value
    return None


def _safe_image(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("/"):
        return value
    if value.lower().startswith(SAFE_IMAGE_SCHEMES):
        host = (urlparse(value).hostname or "").lower()
        if host and host in _allowed_image_hosts():
            return value
    return None


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0
        self._skipped: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in DROP_WITH_CONTENT:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if tag not in ALLOWED_TAGS:
            return

        rendered = self._render_attributes(tag, attrs)
        if rendered is None:
            # 标签本身被丢弃（如非法 href/src），同步跳过其闭合标签
            if tag not in VOID_TAGS:
                self._skipped[tag] = self._skipped.get(tag, 0) + 1
            return
        self.parts.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in DROP_WITH_CONTENT:
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_WITH_CONTENT:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if self._skipped.get(tag):
            self._skipped[tag] -= 1
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._drop_depth or not data:
            return
        self.parts.append(escape(data, quote=False))

    def handle_comment(self, data: str) -> None:  # noqa: ARG002
        return

    def _render_attributes(self, tag: str, attrs) -> str | None:
        allowed = ALLOWED_ATTRIBUTES.get(tag, set())
        values: dict[str, str] = {}
        for name, value in attrs:
            name = (name or "").lower()
            if name.startswith("on") or name not in allowed or value is None:
                continue
            values[name] = value

        if tag == "a":
            href = _safe_link(values.get("href", ""))
            if href is None:
                return None
            values["href"] = href
            if href.lower().startswith(("http://", "https://")):
                return f' href="{escape(href, quote=True)}"' f' rel="noopener noreferrer"' + (
                    f' title="{escape(values["title"], quote=True)}"' if values.get("title") else ""
                )
        if tag == "img":
            src = _safe_image(values.get("src", ""))
            if src is None:
                return None
            values["src"] = src

        rendered = "".join(
            f' {name}="{escape(value, quote=True)}"' for name, value in values.items() if value
        )
        return rendered


def sanitize_html(raw: str) -> str:
    """清洗富文本：仅保留白名单标签与安全属性，丢弃脚本类标签及其内容。"""
    raw = raw or ""
    parser = _Sanitizer()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts).strip()
