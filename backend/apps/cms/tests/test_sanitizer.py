"""T3.2 富文本白名单清洗：危险标签、事件属性与外链图片限制。"""

import pytest

from apps.cms.services import sanitize_html


def test_keeps_allowed_tags_and_text():
    raw = "<h2>标题</h2><p>正文<strong>加粗</strong><em>斜体</em></p><ul><li>条目</li></ul>"
    assert sanitize_html(raw) == raw


def test_strips_script_style_iframe_with_content():
    raw = (
        "<p>前</p><script>alert(1)</script><style>body{display:none}</style>"
        '<iframe src="https://evil.example.com"></iframe><p>后</p>'
    )
    cleaned = sanitize_html(raw)
    assert "script" not in cleaned
    assert "alert(1)" not in cleaned
    assert "display:none" not in cleaned
    assert "iframe" not in cleaned
    assert cleaned == "<p>前</p><p>后</p>"


def test_removes_event_attributes_and_inline_style():
    raw = '<p onclick="alert(1)" style="color:red">正文</p>'
    assert sanitize_html(raw) == "<p>正文</p>"


def test_removes_javascript_href_but_keeps_text():
    raw = '<p><a href="javascript:alert(1)">点我</a></p>'
    assert sanitize_html(raw) == "<p>点我</p>"


def test_external_link_gets_noopener():
    cleaned = sanitize_html('<a href="https://example.com" onclick="x()">链接</a>')
    assert cleaned == '<a href="https://example.com" rel="noopener noreferrer">链接</a>'


def test_drops_external_image_domain_by_default():
    raw = '<p><img src="https://evil.example.com/a.png" alt="x"></p>'
    assert sanitize_html(raw) == "<p></p>"


def test_allows_whitelisted_external_image_host(settings):
    settings.CMS_ALLOWED_IMAGE_HOSTS = ["cdn.example.com"]
    raw = '<img src="https://cdn.example.com/a.png" alt="封面">'
    assert sanitize_html(raw) == '<img src="https://cdn.example.com/a.png" alt="封面">'


def test_keeps_relative_image():
    raw = '<img src="/media/cms/a.png" onerror="alert(1)">'
    assert sanitize_html(raw) == '<img src="/media/cms/a.png">'


def test_drops_data_uri_image():
    raw = '<img src="data:image/svg+xml;base64,PHN2Zz4=">'
    assert sanitize_html(raw) == ""


def test_disallowed_tag_is_unwrapped_but_text_kept():
    assert sanitize_html("<div><span>文字</span></div>") == "文字"


@pytest.mark.parametrize(
    "raw",
    ["<p>未闭合", "<p><strong>错位</p></strong>", "普通文本 & < 符号"],
)
def test_malformed_html_does_not_raise(raw):
    assert isinstance(sanitize_html(raw), str)
